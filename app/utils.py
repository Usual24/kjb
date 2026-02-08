"""Shared helpers for permissions and data utilities."""
from flask import abort
from flask_jwt_extended import get_jwt_identity
from .models import User, ChannelPermission, ChannelMember, Role
from .extensions import db


def get_current_user():
    user_id = get_jwt_identity()
    if not user_id:
        abort(401)
    user = User.query.get(user_id)
    if not user:
        abort(401)
    return user


def require_role(user, role_name):
    if not user.has_role(role_name):
        abort(403)


def ensure_member(channel_id, user_id):
    membership = ChannelMember.query.filter_by(channel_id=channel_id, user_id=user_id).first()
    if not membership:
        abort(403)
    return membership


def ensure_channel_permission(channel_id, user, action):
    if user.has_role("admin"):
        return True
    permission = ChannelPermission.query.filter(
        ChannelPermission.channel_id == channel_id,
        ((ChannelPermission.user_id == user.id) | (ChannelPermission.role_id.in_([r.id for r in user.roles])))
    ).first()
    if not permission:
        abort(403)
    if action == "read" and not permission.can_read:
        abort(403)
    if action == "write" and not permission.can_write:
        abort(403)
    if action == "admin" and not permission.can_admin:
        abort(403)
    return True


def get_or_create_role(name):
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name)
        db.session.add(role)
        db.session.commit()
    return role
