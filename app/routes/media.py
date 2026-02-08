"""Media upload endpoints."""
import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
from ..extensions import db
from ..models import Media
from ..utils import get_current_user

bp = Blueprint("media", __name__, url_prefix="/api/media")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


@bp.post("/upload")
@jwt_required()
def upload_media():
    user = get_current_user()
    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "invalid_file"}), 400
    filename = secure_filename(file.filename)
    os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(path)
    media = Media(uploader_id=user.id, filename=filename, url=f"/api/media/{filename}")
    db.session.add(media)
    db.session.commit()
    return jsonify({"id": media.id, "url": media.url})


@bp.get("/<path:filename>")
def get_media(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
