"""Application factory for KJB chat community."""
from flask import Flask
from .extensions import db, migrate, socketio
from .routes import views
from .sockets import register_socket_handlers
from .utils import init_session, get_current_user
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
        return {
            "current_user": get_current_user(),
            "channels": Channel.query.order_by(Channel.name.asc()).all(),
        }

    with app.app_context():
        db.create_all()
        if not Channel.query.first():
            db.session.add(Channel(slug="general", name="# general", description="기본 채널"))
            db.session.commit()

    register_socket_handlers(socketio)

    return app
