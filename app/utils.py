from functools import wraps
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo
from flask import session, redirect, url_for, g, current_app
from .models import User


def init_session(app):
    app.permanent_session_lifetime = timedelta(days=30)


def get_current_user():
    if hasattr(g, "current_user"):
        return g.current_user
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None
    g.current_user = User.query.get(user_id)
    return g.current_user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for("views.signin"))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or not user.is_admin:
            return redirect(url_for("views.index"))
        return view(*args, **kwargs)

    return wrapper


def set_login(user, remember=False):
    session["user_id"] = user.id
    session.permanent = bool(remember)


def logout_user():
    session.clear()


def notify(user_id, title, body, db, Notification):
    notification = Notification(user_id=user_id, title=title, body=body)
    db.session.add(notification)


def adjust_kc(user, delta, reason, db, KCLog, Notification):
    user.kc_points += delta
    db.session.add(KCLog(user_id=user.id, delta=delta, reason=reason))
    notify(user.id, "KC 변동", f"{reason} ({delta:+d} KC)", db, Notification)


def to_kst(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Seoul"))
