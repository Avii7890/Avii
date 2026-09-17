import config

config.Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

import pytest

from app import app as flask_app
from extensions import db


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
