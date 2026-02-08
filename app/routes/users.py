"""User profile, roles, and friendship endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import User, Friend, Message
from ..utils import get_current_user, require_role

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("/me")
@jwt_required()
def me():
    user = get_current_user()
    return jsonify({
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "status_message": user.status_message,
        "roles": [role.name for role in user.roles],
        "is_online": user.is_online,
    })


@bp.patch("/me")
@jwt_required()
def update_me():
    user = get_current_user()
    data = request.get_json() or {}
    user.nickname = data.get("nickname", user.nickname)
    user.avatar_url = data.get("avatar_url", user.avatar_url)
    user.status_message = data.get("status_message", user.status_message)
    db.session.commit()
    return jsonify({"status": "ok"})


@bp.post("/roles/<int:user_id>")
@jwt_required()
def assign_role(user_id):
    user = get_current_user()
    require_role(user, "admin")
    data = request.get_json() or {}
    role_name = data.get("role")
    target = User.query.get_or_404(user_id)
    if role_name and role_name not in [r.name for r in target.roles]:
        from ..utils import get_or_create_role
        target.roles.append(get_or_create_role(role_name))
        db.session.commit()
    return jsonify({"status": "ok"})


@bp.post("/friends")
@jwt_required()
def add_friend():
    user = get_current_user()
    data = request.get_json() or {}
    friend_id = data.get("friend_id")
    if not friend_id or friend_id == user.id:
        return jsonify({"error": "invalid_friend"}), 400
    if Friend.query.filter_by(user_id=user.id, friend_id=friend_id).first():
        return jsonify({"error": "already_requested"}), 400
    friend = Friend(user_id=user.id, friend_id=friend_id)
    db.session.add(friend)
    db.session.commit()
    return jsonify({"status": "requested"})


@bp.post("/friends/<int:friend_id>/accept")
@jwt_required()
def accept_friend(friend_id):
    user = get_current_user()
    record = Friend.query.filter_by(user_id=friend_id, friend_id=user.id).first_or_404()
    record.status = "accepted"
    db.session.add(Friend(user_id=user.id, friend_id=friend_id, status="accepted"))
    db.session.commit()
    return jsonify({"status": "accepted"})


@bp.get("/friends")
@jwt_required()
def list_friends():
    user = get_current_user()
    friends = Friend.query.filter_by(user_id=user.id, status="accepted").all()
    return jsonify([{"friend_id": f.friend_id} for f in friends])


@bp.post("/dm")
@jwt_required()
def direct_message():
    user = get_current_user()
    data = request.get_json() or {}
    recipient_id = data.get("recipient_id")
    content = data.get("content")
    if not recipient_id or not content:
        return jsonify({"error": "missing_fields"}), 400
    message = Message(sender_id=user.id, recipient_id=recipient_id, content=content)
    db.session.add(message)
    db.session.commit()
    return jsonify({"id": message.id, "created_at": message.created_at.isoformat()})


@bp.get("/dm/<int:friend_id>")
@jwt_required()
def list_dm(friend_id):
    user = get_current_user()
    messages = Message.query.filter(
        ((Message.sender_id == user.id) & (Message.recipient_id == friend_id))
        | ((Message.sender_id == friend_id) & (Message.recipient_id == user.id))
    ).order_by(Message.created_at.asc()).all()
    return jsonify([
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "recipient_id": m.recipient_id,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ])
