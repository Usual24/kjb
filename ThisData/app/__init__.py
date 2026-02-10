"""ThisData community application factory."""
from flask import Flask
from .extensions import db, jwt
from .routes import bp as api_bp


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(api_bp)

    with app.app_context():
        db.create_all()

    return app
