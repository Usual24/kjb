"""Board and forum endpoints."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import or_
from ..extensions import db
from ..models import Post, Comment, PostReaction, Tag, Category
from ..utils import get_current_user

bp = Blueprint("boards", __name__, url_prefix="/api/boards")


@bp.post("/posts")
@jwt_required()
def create_post():
    user = get_current_user()
    data = request.get_json() or {}
    title = data.get("title")
    body = data.get("body")
    category_id = data.get("category_id")
    if not title or not body:
        return jsonify({"error": "missing_fields"}), 400
    post = Post(user_id=user.id, title=title, body=body, category_id=category_id)
    db.session.add(post)
    db.session.flush()
    tags = data.get("tags") or []
    for tag_name in tags:
        tag = Tag.query.filter_by(name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
        post.tags.append(tag)
    db.session.commit()
    return jsonify({"id": post.id})


@bp.get("/posts")
@jwt_required()
def list_posts():
    query = Post.query
    search = request.args.get("search")
    if search:
        query = query.filter(or_(Post.title.contains(search), Post.body.contains(search)))
    if request.args.get("category_id"):
        query = query.filter_by(category_id=request.args.get("category_id"))
    posts = query.order_by(Post.is_pinned.desc(), Post.created_at.desc()).all()
    return jsonify([
        {
            "id": p.id,
            "title": p.title,
            "is_pinned": p.is_pinned,
            "created_at": p.created_at.isoformat(),
        }
        for p in posts
    ])


@bp.get("/posts/<int:post_id>")
@jwt_required()
def get_post(post_id):
    post = Post.query.get_or_404(post_id)
    return jsonify({
        "id": post.id,
        "title": post.title,
        "body": post.body,
        "tags": [tag.name for tag in post.tags],
        "category_id": post.category_id,
    })


@bp.patch("/posts/<int:post_id>")
@jwt_required()
def update_post(post_id):
    user = get_current_user()
    post = Post.query.get_or_404(post_id)
    if post.user_id != user.id and not user.has_role("moderator"):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    post.title = data.get("title", post.title)
    post.body = data.get("body", post.body)
    post.is_pinned = data.get("is_pinned", post.is_pinned)
    db.session.commit()
    return jsonify({"status": "ok"})


@bp.delete("/posts/<int:post_id>")
@jwt_required()
def delete_post(post_id):
    user = get_current_user()
    post = Post.query.get_or_404(post_id)
    if post.user_id != user.id and not user.has_role("moderator"):
        return jsonify({"error": "forbidden"}), 403
    db.session.delete(post)
    db.session.commit()
    return jsonify({"status": "deleted"})


@bp.post("/posts/<int:post_id>/comments")
@jwt_required()
def add_comment(post_id):
    user = get_current_user()
    data = request.get_json() or {}
    body = data.get("body")
    if not body:
        return jsonify({"error": "missing_body"}), 400
    comment = Comment(post_id=post_id, user_id=user.id, body=body, parent_id=data.get("parent_id"))
    db.session.add(comment)
    db.session.commit()
    return jsonify({"id": comment.id})


@bp.get("/posts/<int:post_id>/comments")
@jwt_required()
def list_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    return jsonify([
        {
            "id": c.id,
            "user_id": c.user_id,
            "parent_id": c.parent_id,
            "body": c.body,
        }
        for c in comments
    ])


@bp.post("/posts/<int:post_id>/reactions")
@jwt_required()
def react_post(post_id):
    user = get_current_user()
    data = request.get_json() or {}
    emoji = data.get("emoji")
    if not emoji:
        return jsonify({"error": "missing_emoji"}), 400
    reaction = PostReaction(post_id=post_id, user_id=user.id, emoji=emoji)
    db.session.add(reaction)
    db.session.commit()
    return jsonify({"status": "ok"})


@bp.post("/categories")
@jwt_required()
def create_category():
    user = get_current_user()
    if not user.has_role("admin"):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify({"error": "missing_name"}), 400
    category = Category(name=name)
    db.session.add(category)
    db.session.commit()
    return jsonify({"id": category.id})
