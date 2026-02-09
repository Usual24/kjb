"""Application factory for KJB chat community."""
from flask import Flask
from .extensions import db, migrate, socketio
from .routes import views
from .sockets import register_socket_handlers
from .utils import init_session, get_current_user, media_url, resolve_channel_permissions
from .models import Channel


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    init_session(app)

    app.register_blueprint(views.bp)

    @app.context_processor
    def inject_globals():
        current_user = get_current_user()
        channels = Channel.query.order_by(Channel.priority.desc(), Channel.name.asc()).all()
        if current_user and not current_user.is_admin:
            channels = [
                channel
                for channel in channels
                if resolve_channel_permissions(current_user, channel)["can_view"]
            ]
        return {
            "current_user": current_user,
            "channels": channels,
        }

    @app.template_filter("media")
    def media_filter(value):
        return media_url(value)

    with app.app_context():
        db.create_all()
        if not Channel.query.first():
            db.session.add(Channel(slug="general", name="# general", description="기본 채널"))
            db.session.commit()

    register_socket_handlers(socketio)

    return app
