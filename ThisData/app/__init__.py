from flask import Flask

from .extensions import db


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "thisdata-dev"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///thisdata.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app
