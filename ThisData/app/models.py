from __future__ import annotations

import secrets
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


class Friendship(db.Model):
    __tablename__ = "friendships"
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("requester_id", "receiver_id", name="uq_friend_direction"),
    )

    requester = db.relationship("User", foreign_keys=[requester_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship("ServerMember", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class BotAccount(db.Model):
    __tablename__ = "bot_accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(24))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User")


class Server(db.Model):
    __tablename__ = "servers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), default="")
    is_public = db.Column(db.Boolean, default=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship("User")
    channels = db.relationship("Channel", back_populates="server", cascade="all, delete-orphan")
    members = db.relationship("ServerMember", back_populates="server", cascade="all, delete-orphan")


class InviteLink(db.Model):
    __tablename__ = "invite_links"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(12))
    server_id = db.Column(db.Integer, db.ForeignKey("servers.id"), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    server = db.relationship("Server")
    created_by = db.relationship("User")


class ServerMember(db.Model):
    __tablename__ = "server_members"
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey("servers.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(20), default="member", nullable=False)
    is_banned = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("server_id", "user_id", name="uq_server_member"),)

    server = db.relationship("Server", back_populates="members")
    user = db.relationship("User", back_populates="memberships")


class Channel(db.Model):
    __tablename__ = "channels"
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey("servers.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    server = db.relationship("Server", back_populates="channels")


class ChannelMessage(db.Model):
    __tablename__ = "channel_messages"
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("channels.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    bot_id = db.Column(db.Integer, db.ForeignKey("bot_accounts.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    channel = db.relationship("Channel")
    user = db.relationship("User")
    bot = db.relationship("BotAccount")


class DirectMessage(db.Model):
    __tablename__ = "direct_messages"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])
