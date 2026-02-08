"""Channel and message endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Channel, ChannelMember, Message, MessageReaction, ChannelPermission
from ..utils import get_current_user, ensure_channel_permission, ensure_member

bp = Blueprint("channels", __name__, url_prefix="/api/channels")


@bp.post("")
@jwt_required()
def create_channel():
    user = get_current_user()
    data = request.get_json() or {}
    name = data.get("name")
    kind = data.get("kind", "text")
    if not name:
        return jsonify({"error": "missing_name"}), 400
    channel = Channel(name=name, kind=kind)
    db.session.add(channel)
    db.session.flush()
    db.session.add(ChannelMember(channel_id=channel.id, user_id=user.id))
    db.session.add(ChannelPermission(channel_id=channel.id, user_id=user.id, can_admin=True))
    db.session.commit()
    return jsonify({"id": channel.id, "name": channel.name, "kind": channel.kind})


@bp.get("")
@jwt_required()
def list_channels():
    user = get_current_user()
    memberships = ChannelMember.query.filter_by(user_id=user.id).all()
    channel_ids = [m.channel_id for m in memberships]
    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()
    return jsonify([{"id": c.id, "name": c.name, "kind": c.kind} for c in channels])


@bp.post("/<int:channel_id>/join")
@jwt_required()
def join_channel(channel_id):
    user = get_current_user()
    if ChannelMember.query.filter_by(channel_id=channel_id, user_id=user.id).first():
        return jsonify({"status": "already_member"})
    db.session.add(ChannelMember(channel_id=channel_id, user_id=user.id))
    db.session.commit()
    return jsonify({"status": "joined"})


@bp.get("/<int:channel_id>/messages")
@jwt_required()
def list_messages(channel_id):
    user = get_current_user()
    ensure_channel_permission(channel_id, user, "read")
    ensure_member(channel_id, user.id)
    messages = Message.query.filter_by(channel_id=channel_id).order_by(Message.created_at.asc()).limit(200).all()
    return jsonify([
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ])


@bp.post("/<int:channel_id>/messages")
@jwt_required()
def create_message(channel_id):
    user = get_current_user()
    ensure_channel_permission(channel_id, user, "write")
    ensure_member(channel_id, user.id)
    data = request.get_json() or {}
    content = data.get("content")
    if not content:
        return jsonify({"error": "missing_content"}), 400
    message = Message(channel_id=channel_id, sender_id=user.id, content=content)
    db.session.add(message)
    db.session.commit()
    return jsonify({"id": message.id, "created_at": message.created_at.isoformat()})


@bp.post("/messages/<int:message_id>/reactions")
@jwt_required()
def react_message(message_id):
    user = get_current_user()
    data = request.get_json() or {}
    emoji = data.get("emoji")
    if not emoji:
        return jsonify({"error": "missing_emoji"}), 400
    reaction = MessageReaction(message_id=message_id, user_id=user.id, emoji=emoji)
    db.session.add(reaction)
    db.session.commit()
    return jsonify({"status": "ok"})


@bp.post("/<int:channel_id>/permissions")
@jwt_required()
def update_permissions(channel_id):
    user = get_current_user()
    ensure_channel_permission(channel_id, user, "admin")
    data = request.get_json() or {}
    permission = ChannelPermission(
        channel_id=channel_id,
        role_id=data.get("role_id"),
        user_id=data.get("user_id"),
        can_read=data.get("can_read", True),
        can_write=data.get("can_write", True),
        can_admin=data.get("can_admin", False),
    )
    db.session.add(permission)
    db.session.commit()
    return jsonify({"status": "ok"})
