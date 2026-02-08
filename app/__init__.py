"""Application factory for 공작방(KJB)."""
from flask import Flask
from .extensions import db, jwt, migrate, socketio
from .routes import auth, users, channels, boards, notifications, media, views
from .sockets import register_socket_handlers


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)

    app.register_blueprint(auth.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(channels.bp)
    app.register_blueprint(boards.bp)
    app.register_blueprint(notifications.bp)
    app.register_blueprint(media.bp)
    app.register_blueprint(views.bp)

    register_socket_handlers(socketio)

    return app
