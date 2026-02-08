"""Socket.IO handlers for real-time chat, calls, and notifications."""
from flask import request
from flask_socketio import join_room, leave_room, emit
from .extensions import db
from .models import Message, User, Notification


def register_socket_handlers(socketio):
    @socketio.on("connect")
    def handle_connect():
        user_id = request.args.get("user_id")
        if user_id:
            user = User.query.get(int(user_id))
            if user:
                user.is_online = True
                db.session.commit()
                emit("presence", {"user_id": user.id, "is_online": True}, broadcast=True)

    @socketio.on("disconnect")
    def handle_disconnect():
        user_id = request.args.get("user_id")
        if user_id:
            user = User.query.get(int(user_id))
            if user:
                user.is_online = False
                db.session.commit()
                emit("presence", {"user_id": user.id, "is_online": False}, broadcast=True)

    @socketio.on("join")
    def handle_join(data):
        join_room(data.get("room"))

    @socketio.on("leave")
    def handle_leave(data):
        leave_room(data.get("room"))

    @socketio.on("chat")
    def handle_chat(data):
        message = Message(
            channel_id=data.get("channel_id"),
            sender_id=data.get("sender_id"),
            content=data.get("content"),
        )
        db.session.add(message)
        db.session.commit()
        emit("chat", {
            "id": message.id,
            "channel_id": message.channel_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }, room=f"channel-{message.channel_id}")

    @socketio.on("notify")
    def handle_notify(data):
        notification = Notification(
            user_id=data.get("user_id"),
            kind=data.get("kind"),
            payload=data.get("payload") or {},
        )
        db.session.add(notification)
        db.session.commit()
        emit("notify", {
            "id": notification.id,
            "kind": notification.kind,
            "payload": notification.payload,
        }, room=f"user-{notification.user_id}")

    @socketio.on("call-signal")
    def handle_call_signal(data):
        emit("call-signal", data, room=data.get("room"))
