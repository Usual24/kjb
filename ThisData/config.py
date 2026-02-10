import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.getenv("THISDATA_SECRET_KEY", "thisdata-dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "THISDATA_DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'thisdata.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("THISDATA_JWT_SECRET_KEY", "thisdata-jwt-secret")
