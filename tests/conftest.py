import pytest

from tripmate import create_app
from tripmate.extensions import db


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()


@pytest.fixture()
def auth(client):
    return AuthActions(client)


def post_with_csrf(client, path, data=None, **kwargs):
    payload = dict(data or {})
    with client.session_transaction() as session:
        session.setdefault("_csrf_token", "test-csrf-token")
        payload["_csrf_token"] = session["_csrf_token"]
    return client.post(path, data=payload, **kwargs)


class AuthActions:
    def __init__(self, client):
        self.client = client

    def register(self, username="alice", email="alice@example.com", password="Pass1234"):
        return post_with_csrf(
            self.client,
            "/auth/register",
            {"username": username, "email": email, "password": password, "bio": "热爱旅行。"},
        )

    def login(self, identity="alice", password="Pass1234"):
        return post_with_csrf(
            self.client, "/auth/login", {"identity": identity, "password": password}
        )

    def logout(self):
        return post_with_csrf(self.client, "/auth/logout")


def create_trip(client, **overrides):
    data = {
        "destination": "日本 · 东京",
        "start_date": "2026-10-10",
        "end_date": "2026-10-15",
        "style": "城市探索",
        "description": "一起看展、散步和拍照，行程节奏轻松。",
        "expected_companions": "2",
    }
    data.update(overrides)
    return post_with_csrf(client, "/trips/new", data)

