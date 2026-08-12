from sqlalchemy import select

from tripmate.extensions import db
from tripmate.models import User

from .conftest import post_with_csrf


def test_registration_hashes_password_and_starts_session(app, client, auth):
    response = auth.register()
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/trips")

    with app.app_context():
        user = db.session.scalar(select(User).where(User.username == "alice"))
        assert user is not None
        assert user.password_hash != "Pass1234"
        assert user.check_password("Pass1234")

    page = client.get("/trips")
    assert page.status_code == 200
    assert "发现下一段旅程" in page.get_data(as_text=True)


def test_duplicate_registration_is_rejected(app, auth):
    auth.register()
    auth.logout()
    response = auth.register(email="other@example.com")
    assert response.status_code == 200
    assert "用户名或邮箱已被使用" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(select(db.func.count(User.id))) == 1


def test_registration_validation_and_login_failure(client, auth):
    response = auth.register(username="x", password="short")
    assert "用户名长度应为" in response.get_data(as_text=True)

    auth.register()
    auth.logout()
    response = auth.login(password="Wrong123")
    assert response.status_code == 200
    assert "密码不正确" in response.get_data(as_text=True)


def test_protected_page_redirects_and_csrf_is_required(client):
    response = client.get("/trips")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    response = client.post(
        "/auth/register",
        data={"username": "alice", "email": "alice@example.com", "password": "Pass1234"},
    )
    assert response.status_code == 400
    assert "表单已过期" in response.get_data(as_text=True)


def test_login_accepts_email_and_logout_clears_session(client, auth):
    auth.register()
    auth.logout()
    response = auth.login(identity="alice@example.com")
    assert response.status_code == 302
    assert client.get("/trips").status_code == 200
    auth.logout()
    assert client.get("/trips").status_code == 302


def test_external_next_url_is_not_used(client, auth):
    auth.register()
    auth.logout()
    response = post_with_csrf(
        client,
        "/auth/login?next=https://evil.example",
        {"identity": "alice", "password": "Pass1234"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/trips")

