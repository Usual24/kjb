from functools import wraps
from flask import request, g, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from .models import User, BotCredential


def auth_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = request.headers.get("X-Bot-Token")
        if token:
            bot_cred = BotCredential.query.filter_by(token=token).first()
            if not bot_cred:
                return jsonify({"error": "invalid bot token"}), 401
            user = User.query.get(bot_cred.user_id)
            if not user or not user.is_bot:
                return jsonify({"error": "bot unavailable"}), 401
            g.current_user = user
            g.auth_type = "bot"
            return view(*args, **kwargs)

        verify_jwt_in_request()
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "user not found"}), 401
        g.current_user = user
        g.auth_type = "user"
        return view(*args, **kwargs)

    return wrapper
