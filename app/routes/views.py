"""Jinja UI routes."""
from flask import Blueprint, render_template

bp = Blueprint("views", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/login")
def login():
    return render_template("login.html")


@bp.get("/register")
def register():
    return render_template("register.html")


@bp.get("/channel")
def channel():
    return render_template("chat.html")


@bp.get("/board")
def board():
    return render_template("board.html")
