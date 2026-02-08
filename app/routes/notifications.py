"""Notification endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Notification, NotificationSetting
from ..utils import get_current_user

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@jwt_required()
def list_notifications():
    user = get_current_user()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(100)
    return jsonify([
        {
            "id": n.id,
            "kind": n.kind,
            "payload": n.payload,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ])


@bp.post("/<int:notification_id>/read")
@jwt_required()
def mark_read(notification_id):
    user = get_current_user()
    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    return jsonify({"status": "ok"})


@bp.post("/settings")
@jwt_required()
def update_setting():
    user = get_current_user()
    data = request.get_json() or {}
    channel_id = data.get("channel_id")
    is_muted = data.get("is_muted", False)
    if not channel_id:
        return jsonify({"error": "missing_channel"}), 400
    setting = NotificationSetting.query.filter_by(user_id=user.id, channel_id=channel_id).first()
    if not setting:
        setting = NotificationSetting(user_id=user.id, channel_id=channel_id)
        db.session.add(setting)
    setting.is_muted = is_muted
    db.session.commit()
    return jsonify({"status": "ok"})
