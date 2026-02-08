"""Authentication endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from ..extensions import db
from ..models import User
from ..utils import get_or_create_role

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    nickname = data.get("nickname")
    if not all([email, password, nickname]):
        return jsonify({"error": "missing_fields"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email_exists"}), 400
    user = User(email=email, nickname=nickname)
    user.set_password(password)
    member_role = get_or_create_role("member")
    user.roles.append(member_role)
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=user.id)
    return jsonify({"access_token": token, "user_id": user.id})


@bp.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid_credentials"}), 401
    token = create_access_token(identity=user.id)
    return jsonify({"access_token": token, "user_id": user.id})
