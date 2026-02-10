from __future__ import annotations

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, session, url_for

from .extensions import db
from .models import (
    BotAccount,
    Channel,
    ChannelMessage,
    DirectMessage,
    Friendship,
    InviteLink,
    Server,
    ServerMember,
    User,
)

bp = Blueprint("views", __name__)


def current_user() -> User | None:
    uid = session.get("user_id")
    if not uid:
        return None
    return User.query.get(uid)


def require_login() -> User:
    user = current_user()
    if not user:
        abort(401)
    return user


def get_membership(user_id: int, server_id: int) -> ServerMember | None:
    return ServerMember.query.filter_by(user_id=user_id, server_id=server_id, is_banned=False).first()


@bp.route("/")
def index():
    user = current_user()
    if not user:
        return render_template("auth.html")

    memberships = (
        ServerMember.query.filter_by(user_id=user.id, is_banned=False)
        .join(Server)
        .order_by(Server.created_at.desc())
        .all()
    )
    public_servers = Server.query.filter_by(is_public=True).order_by(Server.created_at.desc()).all()
    server_id = request.args.get("server", type=int)
    active_membership = memberships[0] if memberships else None
    if server_id:
        selected = next((m for m in memberships if m.server_id == server_id), None)
        if selected:
            active_membership = selected

    channels = []
    messages = []
    active_channel_id = request.args.get("channel", type=int)
    if active_membership:
        channels = Channel.query.filter_by(server_id=active_membership.server_id).order_by(Channel.id.asc()).all()
        if channels:
            if not active_channel_id:
                active_channel_id = channels[0].id
            active_channel = next((c for c in channels if c.id == active_channel_id), channels[0])
            active_channel_id = active_channel.id
            messages = ChannelMessage.query.filter_by(channel_id=active_channel_id).order_by(ChannelMessage.created_at.asc()).all()

    users = User.query.filter(User.id != user.id).order_by(User.username.asc()).all()
    friendships = Friendship.query.filter(
        ((Friendship.requester_id == user.id) | (Friendship.receiver_id == user.id))
    ).all()

    friend_ids = set()
    pending_requests = []
    for f in friendships:
        if f.status == "accepted":
            friend_ids.add(f.requester_id if f.requester_id != user.id else f.receiver_id)
        elif f.status == "pending" and f.receiver_id == user.id:
            pending_requests.append(f)

    dm_target_id = request.args.get("dm", type=int)
    dm_messages = []
    if dm_target_id and dm_target_id in friend_ids:
        dm_messages = (
            DirectMessage.query.filter(
                ((DirectMessage.sender_id == user.id) & (DirectMessage.receiver_id == dm_target_id))
                | ((DirectMessage.sender_id == dm_target_id) & (DirectMessage.receiver_id == user.id))
            )
            .order_by(DirectMessage.created_at.asc())
            .all()
        )

    bot_accounts = BotAccount.query.filter_by(owner_id=user.id).all()

    return render_template(
        "index.html",
        user=user,
        memberships=memberships,
        public_servers=public_servers,
        active_membership=active_membership,
        channels=channels,
        active_channel_id=active_channel_id,
        messages=messages,
        users=users,
        friend_ids=friend_ids,
        pending_requests=pending_requests,
        dm_target_id=dm_target_id,
        dm_messages=dm_messages,
        bot_accounts=bot_accounts,
    )


@bp.post("/signup")
def signup():
    username = request.form["username"].strip()
    display_name = request.form["display_name"].strip()
    password = request.form["password"]
    if User.query.filter_by(username=username).first():
        flash("이미 존재하는 사용자명입니다.")
        return redirect(url_for("views.index"))

    user = User(username=username, display_name=display_name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session["user_id"] = user.id
    return redirect(url_for("views.index"))


@bp.post("/login")
def login():
    username = request.form["username"].strip()
    password = request.form["password"]
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        flash("로그인 실패")
        return redirect(url_for("views.index"))
    session["user_id"] = user.id
    return redirect(url_for("views.index"))


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("views.index"))


@bp.post("/servers/create")
def create_server():
    user = require_login()
    name = request.form["name"].strip()
    is_public = request.form.get("is_public") == "on"
    server = Server(name=name, is_public=is_public, owner_id=user.id)
    db.session.add(server)
    db.session.flush()
    db.session.add(ServerMember(server_id=server.id, user_id=user.id, role="admin"))
    db.session.add(Channel(server_id=server.id, name="general"))
    db.session.commit()
    return redirect(url_for("views.index", server=server.id))


@bp.post("/channels/create")
def create_channel():
    user = require_login()
    server_id = int(request.form["server_id"])
    membership = get_membership(user.id, server_id)
    if not membership or membership.role != "admin":
        abort(403)
    channel = Channel(server_id=server_id, name=request.form["name"].strip())
    db.session.add(channel)
    db.session.commit()
    return redirect(url_for("views.index", server=server_id, channel=channel.id))


@bp.post("/messages/send")
def send_message():
    user = require_login()
    channel_id = int(request.form["channel_id"])
    channel = Channel.query.get_or_404(channel_id)
    membership = get_membership(user.id, channel.server_id)
    if not membership:
        abort(403)
    db.session.add(ChannelMessage(channel_id=channel_id, user_id=user.id, content=request.form["content"].strip()))
    db.session.commit()
    return redirect(url_for("views.index", server=channel.server_id, channel=channel_id))


@bp.get("/invite")
def join_by_invite():
    user = require_login()
    code = request.args.get("code", "")
    invite = InviteLink.query.filter_by(code=code, is_active=True).first_or_404()
    existing = ServerMember.query.filter_by(server_id=invite.server_id, user_id=user.id).first()
    if existing:
        if existing.is_banned:
            abort(403)
        return redirect(url_for("views.index", server=invite.server_id))

    db.session.add(ServerMember(server_id=invite.server_id, user_id=user.id, role="member"))
    db.session.commit()
    return redirect(url_for("views.index", server=invite.server_id))


@bp.post("/servers/<int:server_id>/join")
def join_public_server(server_id: int):
    user = require_login()
    server = Server.query.get_or_404(server_id)
    if not server.is_public:
        abort(403)
    existing = ServerMember.query.filter_by(server_id=server_id, user_id=user.id).first()
    if existing:
        if existing.is_banned:
            abort(403)
        return redirect(url_for("views.index", server=server_id))

    db.session.add(ServerMember(server_id=server_id, user_id=user.id, role="member"))
    db.session.commit()
    return redirect(url_for("views.index", server=server_id))


@bp.post("/servers/<int:server_id>/invite")
def create_invite(server_id: int):
    user = require_login()
    membership = get_membership(user.id, server_id)
    if not membership or membership.role != "admin":
        abort(403)
    invite = InviteLink(server_id=server_id, created_by_id=user.id)
    db.session.add(invite)
    db.session.commit()
    flash(f"초대 링크: /invite?code={invite.code}")
    return redirect(url_for("views.index", server=server_id))


@bp.post("/servers/<int:server_id>/ban")
def ban_member(server_id: int):
    user = require_login()
    membership = get_membership(user.id, server_id)
    if not membership or membership.role != "admin":
        abort(403)

    target_id = int(request.form["target_id"])
    target_membership = ServerMember.query.filter_by(server_id=server_id, user_id=target_id).first_or_404()
    target_membership.is_banned = True
    db.session.commit()
    return redirect(url_for("views.index", server=server_id))


@bp.post("/friends/request")
def request_friend():
    user = require_login()
    target_id = int(request.form["target_id"])
    if user.id == target_id:
        return redirect(url_for("views.index"))

    a, b = sorted([user.id, target_id])
    existing = Friendship.query.filter(
        ((Friendship.requester_id == a) & (Friendship.receiver_id == b))
        | ((Friendship.requester_id == b) & (Friendship.receiver_id == a))
    ).first()
    if not existing:
        db.session.add(Friendship(requester_id=user.id, receiver_id=target_id, status="pending"))
        db.session.commit()
    return redirect(url_for("views.index"))


@bp.post("/friends/accept")
def accept_friend():
    user = require_login()
    friendship = Friendship.query.get_or_404(int(request.form["friendship_id"]))
    if friendship.receiver_id != user.id:
        abort(403)
    friendship.status = "accepted"
    db.session.commit()
    return redirect(url_for("views.index"))


@bp.post("/dm/send")
def send_dm():
    user = require_login()
    target_id = int(request.form["target_id"])
    friendship = Friendship.query.filter(
        Friendship.status == "accepted",
        ((Friendship.requester_id == user.id) & (Friendship.receiver_id == target_id))
        | ((Friendship.requester_id == target_id) & (Friendship.receiver_id == user.id)),
    ).first()
    if not friendship:
        abort(403)
    db.session.add(DirectMessage(sender_id=user.id, receiver_id=target_id, content=request.form["content"].strip()))
    db.session.commit()
    return redirect(url_for("views.index", dm=target_id))


@bp.post("/bots/create")
def create_bot():
    user = require_login()
    bot = BotAccount(name=request.form["name"].strip(), owner_id=user.id)
    db.session.add(bot)
    db.session.commit()
    flash(f"봇 토큰: {bot.token}")
    return redirect(url_for("views.index"))


@bp.get("/api/bot/messages")
def bot_get_messages():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    channel_id = request.args.get("channel_id", type=int)
    bot = BotAccount.query.filter_by(token=token).first()
    if not bot:
        return jsonify({"error": "invalid_token"}), 401
    channel = Channel.query.get_or_404(channel_id)
    owner_membership = get_membership(bot.owner_id, channel.server_id)
    if not owner_membership:
        return jsonify({"error": "owner_not_member"}), 403
    rows = ChannelMessage.query.filter_by(channel_id=channel.id).order_by(ChannelMessage.created_at.desc()).limit(50).all()
    data = [
        {
            "id": row.id,
            "content": row.content,
            "author": row.user.display_name if row.user else row.bot.name,
            "created_at": row.created_at.isoformat(),
        }
        for row in reversed(rows)
    ]
    return jsonify({"messages": data})


@bp.post("/api/bot/messages")
def bot_send_message():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = request.get_json(silent=True) or {}
    channel_id = payload.get("channel_id")
    content = (payload.get("content") or "").strip()
    bot = BotAccount.query.filter_by(token=token).first()
    if not bot:
        return jsonify({"error": "invalid_token"}), 401
    if not channel_id or not content:
        return jsonify({"error": "missing_payload"}), 400
    channel = Channel.query.get_or_404(channel_id)
    owner_membership = get_membership(bot.owner_id, channel.server_id)
    if not owner_membership:
        return jsonify({"error": "owner_not_member"}), 403

    msg = ChannelMessage(channel_id=channel.id, bot_id=bot.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({"status": "sent", "message_id": msg.id})
