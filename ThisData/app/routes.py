from flask import Blueprint, jsonify, request, g
from flask_jwt_extended import create_access_token
from sqlalchemy import or_, and_

from .extensions import db
from .auth import auth_required
from .models import (
    User,
    CommunityServer,
    ServerMembership,
    ServerChannel,
    ChannelMessage,
    InviteLink,
    ServerBan,
    Friendship,
    FriendRequest,
    DirectMessage,
    BotCredential,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def _membership(server_id: int, user_id: int):
    return ServerMembership.query.filter_by(server_id=server_id, user_id=user_id).first()


def _is_admin(server_id: int, user_id: int) -> bool:
    member = _membership(server_id, user_id)
    return bool(member and member.role == "admin")


def _is_banned(server_id: int, user_id: int) -> bool:
    return ServerBan.query.filter_by(server_id=server_id, user_id=user_id).first() is not None


@bp.get("/health")
def health():
    return jsonify({"community": "ThisData", "status": "ok"})


@bp.post("/auth/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    username = (payload.get("username") or "").strip()
    display_name = (payload.get("display_name") or "").strip()
    password = payload.get("password") or ""
    if not all([email, username, display_name, password]):
        return jsonify({"error": "missing required fields"}), 400
    if User.query.filter(or_(User.email == email, User.username == username)).first():
        return jsonify({"error": "email or username already used"}), 409
    user = User(email=email, username=username, display_name=display_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username}), 201


@bp.post("/auth/signin")
def signin():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    user = User.query.filter_by(email=email, is_bot=False).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "user": {"id": user.id, "username": user.username}})


@bp.post("/servers")
@auth_required
def create_server():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    is_public = bool(payload.get("is_public", False))
    if not name:
        return jsonify({"error": "name is required"}), 400

    server = CommunityServer(
        name=name, description=description, is_public=is_public, creator_id=g.current_user.id
    )
    db.session.add(server)
    db.session.flush()
    db.session.add(ServerMembership(server_id=server.id, user_id=g.current_user.id, role="admin"))
    db.session.add(ServerChannel(server_id=server.id, name="general"))
    db.session.commit()
    return jsonify({"server_id": server.id, "name": server.name, "is_public": server.is_public}), 201


@bp.get("/servers")
@auth_required
def list_servers():
    memberships = ServerMembership.query.filter_by(user_id=g.current_user.id).all()
    servers = []
    for membership in memberships:
        server = CommunityServer.query.get(membership.server_id)
        channels = ServerChannel.query.filter_by(server_id=server.id).all()
        servers.append(
            {
                "id": server.id,
                "name": server.name,
                "is_public": server.is_public,
                "role": membership.role,
                "channels": [{"id": c.id, "name": c.name} for c in channels],
            }
        )
    return jsonify({"servers": servers})


@bp.post("/servers/<int:server_id>/channels")
@auth_required
def create_channel(server_id: int):
    if not _is_admin(server_id, g.current_user.id):
        return jsonify({"error": "admin required"}), 403
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    channel = ServerChannel(server_id=server_id, name=name)
    db.session.add(channel)
    db.session.commit()
    return jsonify({"id": channel.id, "name": channel.name}), 201


@bp.get("/servers/<int:server_id>/channels/<int:channel_id>/messages")
@auth_required
def read_channel_messages(server_id: int, channel_id: int):
    if not _membership(server_id, g.current_user.id):
        return jsonify({"error": "membership required"}), 403
    messages = (
        ChannelMessage.query.filter_by(channel_id=channel_id)
        .order_by(ChannelMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return jsonify(
        {
            "messages": [
                {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ]
        }
    )


@bp.post("/servers/<int:server_id>/channels/<int:channel_id>/messages")
@auth_required
def send_channel_message(server_id: int, channel_id: int):
    if not _membership(server_id, g.current_user.id):
        return jsonify({"error": "membership required"}), 403
    if _is_banned(server_id, g.current_user.id):
        return jsonify({"error": "you are banned from this server"}), 403
    payload = request.get_json(silent=True) or {}
    content = (payload.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400
    msg = ChannelMessage(channel_id=channel_id, sender_id=g.current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({"id": msg.id, "content": msg.content}), 201


@bp.post("/servers/<int:server_id>/invite-links")
@auth_required
def create_invite(server_id: int):
    if not _is_admin(server_id, g.current_user.id):
        return jsonify({"error": "admin required"}), 403
    invite = InviteLink(
        server_id=server_id, code=InviteLink.new_code(), created_by_id=g.current_user.id, is_active=True
    )
    db.session.add(invite)
    db.session.commit()
    return jsonify({"invite_url": f"/invite?code={invite.code}", "code": invite.code}), 201


@bp.get("/invite")
@auth_required
def inspect_invite():
    code = request.args.get("code", "")
    invite = InviteLink.query.filter_by(code=code, is_active=True).first()
    if not invite:
        return jsonify({"error": "invite not found"}), 404
    server = CommunityServer.query.get(invite.server_id)
    return jsonify({"server_id": server.id, "server_name": server.name, "is_public": server.is_public})


@bp.post("/invite")
@auth_required
def accept_invite():
    payload = request.get_json(silent=True) or {}
    code = payload.get("code") or ""
    invite = InviteLink.query.filter_by(code=code, is_active=True).first()
    if not invite:
        return jsonify({"error": "invite not found"}), 404
    if _is_banned(invite.server_id, g.current_user.id):
        return jsonify({"error": "banned from this server"}), 403
    if _membership(invite.server_id, g.current_user.id):
        return jsonify({"status": "already_member"})
    db.session.add(ServerMembership(server_id=invite.server_id, user_id=g.current_user.id, role="member"))
    db.session.commit()
    return jsonify({"status": "joined", "server_id": invite.server_id})


@bp.post("/servers/<int:server_id>/join-public")
@auth_required
def join_public_server(server_id: int):
    server = CommunityServer.query.get(server_id)
    if not server or not server.is_public:
        return jsonify({"error": "public server not found"}), 404
    if _is_banned(server_id, g.current_user.id):
        return jsonify({"error": "banned from this server"}), 403
    if _membership(server_id, g.current_user.id):
        return jsonify({"status": "already_member"})
    db.session.add(ServerMembership(server_id=server_id, user_id=g.current_user.id, role="member"))
    db.session.commit()
    return jsonify({"status": "joined", "server_id": server_id})


@bp.post("/servers/<int:server_id>/ban")
@auth_required
def ban_user(server_id: int):
    if not _is_admin(server_id, g.current_user.id):
        return jsonify({"error": "admin required"}), 403
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    reason = (payload.get("reason") or "").strip()
    target_membership = _membership(server_id, user_id)
    if not target_membership:
        return jsonify({"error": "target user is not a member"}), 404
    if target_membership.role == "admin":
        return jsonify({"error": "cannot ban another admin"}), 400
    if not _is_banned(server_id, user_id):
        db.session.add(ServerBan(server_id=server_id, user_id=user_id, banned_by_id=g.current_user.id, reason=reason))
    ServerMembership.query.filter_by(server_id=server_id, user_id=user_id).delete()
    db.session.commit()
    return jsonify({"status": "banned", "user_id": user_id})


@bp.post("/friends/request")
@auth_required
def send_friend_request():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    target = User.query.filter_by(username=username, is_bot=False).first()
    if not target or target.id == g.current_user.id:
        return jsonify({"error": "invalid target"}), 400
    if Friendship.query.filter_by(user_id=g.current_user.id, friend_id=target.id).first():
        return jsonify({"status": "already_friends"})
    existing = FriendRequest.query.filter_by(sender_id=g.current_user.id, receiver_id=target.id, status="pending").first()
    if existing:
        return jsonify({"status": "already_requested"})
    db.session.add(FriendRequest(sender_id=g.current_user.id, receiver_id=target.id))
    db.session.commit()
    return jsonify({"status": "requested"}), 201


@bp.post("/friends/request/<int:request_id>/accept")
@auth_required
def accept_friend_request(request_id: int):
    friend_request = FriendRequest.query.get(request_id)
    if not friend_request or friend_request.receiver_id != g.current_user.id:
        return jsonify({"error": "request not found"}), 404
    if friend_request.status != "pending":
        return jsonify({"error": "already handled"}), 400
    friend_request.status = "accepted"
    db.session.add(Friendship(user_id=friend_request.sender_id, friend_id=friend_request.receiver_id))
    db.session.add(Friendship(user_id=friend_request.receiver_id, friend_id=friend_request.sender_id))
    db.session.commit()
    return jsonify({"status": "accepted"})


@bp.get("/friends")
@auth_required
def list_friends():
    friendships = Friendship.query.filter_by(user_id=g.current_user.id).all()
    friend_ids = [f.friend_id for f in friendships]
    users = User.query.filter(User.id.in_(friend_ids)).all() if friend_ids else []
    return jsonify({"friends": [{"id": u.id, "username": u.username, "display_name": u.display_name} for u in users]})


@bp.post("/dm")
@auth_required
def send_dm():
    payload = request.get_json(silent=True) or {}
    receiver_id = payload.get("receiver_id")
    content = (payload.get("content") or "").strip()
    if not receiver_id or not content:
        return jsonify({"error": "receiver_id and content are required"}), 400
    if not Friendship.query.filter_by(user_id=g.current_user.id, friend_id=receiver_id).first():
        return jsonify({"error": "dm is only allowed between friends"}), 403
    dm = DirectMessage(sender_id=g.current_user.id, receiver_id=receiver_id, content=content)
    db.session.add(dm)
    db.session.commit()
    return jsonify({"id": dm.id, "content": dm.content}), 201


@bp.get("/dm/<int:user_id>")
@auth_required
def read_dm(user_id: int):
    if not Friendship.query.filter_by(user_id=g.current_user.id, friend_id=user_id).first():
        return jsonify({"error": "dm is only allowed between friends"}), 403
    messages = (
        DirectMessage.query.filter(
            or_(
                and_(DirectMessage.sender_id == g.current_user.id, DirectMessage.receiver_id == user_id),
                and_(DirectMessage.sender_id == user_id, DirectMessage.receiver_id == g.current_user.id),
            )
        )
        .order_by(DirectMessage.created_at.asc())
        .all()
    )
    return jsonify(
        {
            "messages": [
                {
                    "id": m.id,
                    "sender_id": m.sender_id,
                    "receiver_id": m.receiver_id,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ]
        }
    )


@bp.post("/bots")
@auth_required
def create_bot():
    payload = request.get_json(silent=True) or {}
    bot_name = (payload.get("username") or "").strip()
    display_name = (payload.get("display_name") or bot_name or "")
    server_id = payload.get("server_id")
    if not bot_name or not server_id:
        return jsonify({"error": "username and server_id are required"}), 400
    if not _is_admin(server_id, g.current_user.id):
        return jsonify({"error": "admin required"}), 403
    if User.query.filter_by(username=bot_name).first():
        return jsonify({"error": "username already used"}), 409

    bot_user = User(
        email=f"{bot_name}-{BotCredential.new_token()[:8]}@bot.thisdata.local",
        username=bot_name,
        display_name=display_name,
        is_bot=True,
        password_hash="!bot!",
    )
    db.session.add(bot_user)
    db.session.flush()

    token = BotCredential.new_token()
    db.session.add(BotCredential(user_id=bot_user.id, token=token, owner_id=g.current_user.id))
    db.session.add(ServerMembership(server_id=server_id, user_id=bot_user.id, role="member"))
    db.session.commit()
    return jsonify({"bot_user_id": bot_user.id, "bot_token": token}), 201
