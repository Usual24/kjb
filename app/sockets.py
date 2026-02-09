from datetime import datetime
from flask import session
from flask_socketio import join_room, leave_room, emit
from .extensions import db
from .models import Message, Channel, User, KCLog, Notification
from .utils import adjust_kc, to_kst, resolve_channel_permissions, media_url


online_users = set()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def register_socket_handlers(socketio):
    @socketio.on("connect")
    def handle_connect():
        user = _current_user()
        if not user:
            return False
        online_users.add(user.id)
        emit("online_update", _online_payload(), broadcast=True)

    @socketio.on("disconnect")
    def handle_disconnect():
        user = _current_user()
        if user and user.id in online_users:
            online_users.discard(user.id)
            emit("online_update", _online_payload(), broadcast=True)

    @socketio.on("join")
    def handle_join(data):
        user = _current_user()
        if not user:
            return
        channel_slug = data.get("channel")
        if not channel_slug:
            return
        channel = Channel.query.filter_by(slug=channel_slug).first()
        if not channel:
            return
        if not resolve_channel_permissions(user, channel)["can_view"]:
            return
        join_room(channel_slug)

    @socketio.on("leave")
    def handle_leave(data):
        channel_slug = data.get("channel")
        if not channel_slug:
            return
        leave_room(channel_slug)

    @socketio.on("send_message")
    def handle_send_message(data):
        user = _current_user()
        if not user:
            return
        channel_slug = data.get("channel")
        content = (data.get("content") or "").strip()
        reply_to_id = data.get("reply_to")
        if not channel_slug or not content:
            return
        channel = Channel.query.filter_by(slug=channel_slug).first()
        if not channel:
            return
        if not resolve_channel_permissions(user, channel)["can_send"]:
            return
        message = Message(
            channel_id=channel.id,
            user_id=user.id,
            content=content,
            reply_to_id=reply_to_id,
        )
        db.session.add(message)
        adjust_kc(user, 1, "채팅 보상", db, KCLog, Notification)
        db.session.commit()
        payload = serialize_message(message)
        emit("new_message", payload, room=channel_slug)

    @socketio.on("edit_message")
    def handle_edit_message(data):
        user = _current_user()
        if not user:
            return
        message_id = data.get("message_id")
        content = (data.get("content") or "").strip()
        if not message_id or not content:
            return
        message = Message.query.get(message_id)
        if not message or message.is_deleted:
            return
        if message.user_id != user.id:
            return
        message.content = content
        message.updated_at = datetime.utcnow()
        db.session.commit()
        emit("message_updated", serialize_message(message), room=_channel_slug(message))

    @socketio.on("delete_message")
    def handle_delete_message(data):
        user = _current_user()
        if not user:
            return
        message_id = data.get("message_id")
        message = Message.query.get(message_id)
        if not message:
            return
        if message.user_id != user.id and not user.is_admin:
            return
        message.is_deleted = True
        message.content = "[삭제됨]"
        db.session.commit()
        emit("message_deleted", {"message_id": message.id}, room=_channel_slug(message))


def serialize_message(message):
    created_at = to_kst(message.created_at)
    updated_at = to_kst(message.updated_at) if message.updated_at else None
    return {
        "id": message.id,
        "channel_id": message.channel_id,
        "user_id": message.user_id,
        "user_name": message.user.name,
        "user_prefix": message.user.email_prefix,
        "avatar": media_url(message.user.avatar_url),
        "content": message.content,
        "reply_to": message.reply_to.content if message.reply_to else None,
        "is_deleted": message.is_deleted,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else None,
    }


def _online_payload():
    users = User.query.filter(User.id.in_(online_users)).all() if online_users else []
    return [
        {
            "id": user.id,
            "name": user.name,
            "email_prefix": user.email_prefix,
            "avatar": media_url(user.avatar_url),
        }
        for user in users
    ]


def _channel_slug(message):
    channel = Channel.query.get(message.channel_id)
    return channel.slug if channel else "general"
