import pytest
from sqlalchemy import select

from tripmate import create_app
from tripmate.extensions import db
from tripmate.models import JoinRequest, Trip


def test_health_endpoint_is_public_lightweight_json(client):
    assert client.application.config["DEEPSEEK_API_KEY"] == ""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "service": "TripMate"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_guest_home_preview_and_javascript_are_browser_usable(client):
    response = client.get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "想去的地方" in page
    assert "开始计划" in page

    script = client.get("/static/js/app.js")
    assert script.status_code == 200
    assert script.mimetype == "application/javascript"
    assert script.headers["X-Content-Type-Options"] == "nosniff"


def test_404_uses_friendly_project_page_without_traceback(client):
    response = client.get("/does-not-exist")
    page = response.get_data(as_text=True)

    assert response.status_code == 404
    assert "没有找到这个页面" in page
    assert "Traceback" not in page


def test_500_uses_friendly_page_without_exception_details(app, client):
    app.config["PROPAGATE_EXCEPTIONS"] = False

    @app.get("/_readiness-test-error")
    def readiness_test_error():
        raise RuntimeError("private diagnostic must not be rendered")

    response = client.get("/_readiness-test-error")
    page = response.get_data(as_text=True)

    assert response.status_code == 500
    assert "服务暂时遇到问题" in page
    assert "private diagnostic" not in page
    assert "Traceback" not in page


def test_production_requires_a_non_default_secret(monkeypatch):
    monkeypatch.delenv("TRIPMATE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY must be configured in production"):
        create_app({"APP_ENV": "production", "SQLALCHEMY_DATABASE_URI": "sqlite://"})


def test_production_enforces_secure_cookie_and_safe_flags():
    production_app = create_app(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "portfolio-production-test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "DEBUG": True,
            "TESTING": True,
            "SESSION_COOKIE_SECURE": False,
        }
    )

    assert production_app.debug is False
    assert production_app.testing is False
    assert production_app.config["SESSION_COOKIE_NAME"] == "tripmate_session"
    assert production_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert production_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert production_app.config["SESSION_COOKIE_SECURE"] is True


def test_demo_requires_a_non_default_secret(monkeypatch):
    monkeypatch.delenv("TRIPMATE_SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY must be configured"):
        create_app({"APP_ENV": "demo", "SQLALCHEMY_DATABASE_URI": "sqlite://"})


def test_demo_inherits_production_security_flags():
    demo_app = create_app(
        {
            "APP_ENV": "demo",
            "SECRET_KEY": "portfolio-demo-test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "DEBUG": True,
            "TESTING": True,
            "SESSION_COOKIE_SECURE": False,
        }
    )

    assert demo_app.config["APP_ENV"] == "demo"
    assert demo_app.debug is False
    assert demo_app.testing is False
    assert demo_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert demo_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert demo_app.config["SESSION_COOKIE_SECURE"] is True


def test_development_config_still_supports_local_http():
    development_app = create_app(
        {
            "APP_ENV": "development",
            "TESTING": True,
            "SECRET_KEY": "development-test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    assert development_app.config["APP_ENV"] == "development"
    assert development_app.config["SESSION_COOKIE_SECURE"] is False
    assert "agent.travel_assistant" in development_app.view_functions


def test_database_url_environment_override_is_supported(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///portfolio-tripmate.db")

    configured_app = create_app(
        {"TESTING": True, "SECRET_KEY": "test-secret"}
    )

    assert configured_app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///portfolio-tripmate.db"


def test_seed_demo_is_disabled_in_production():
    production_app = create_app(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "portfolio-production-test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    result = production_app.test_cli_runner().invoke(args=["seed-demo"])

    assert result.exit_code != 0
    assert "disabled in production" in result.output


def test_seed_demo_is_allowed_by_explicit_demo_command():
    demo_app = create_app(
        {
            "APP_ENV": "demo",
            "SECRET_KEY": "portfolio-demo-test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )
    with demo_app.app_context():
        db.create_all()
    try:
        result = demo_app.test_cli_runner().invoke(args=["seed-demo"])
        assert result.exit_code == 0, result.output
        assert "已创建 3 个演示账号" in result.output
    finally:
        with demo_app.app_context():
            db.session.remove()
            db.drop_all()


def test_demo_seed_covers_portfolio_lifecycle_states(app, runner):
    result = runner.invoke(args=["seed-demo"])
    assert result.exit_code == 0

    with app.app_context():
        trip_statuses = set(db.session.scalars(select(Trip.status)).all())
        request_statuses = set(db.session.scalars(select(JoinRequest.status)).all())

    assert trip_statuses == {"OPEN", "CLOSED", "CANCELLED"}
    assert request_statuses == {
        "PENDING",
        "ACCEPTED",
        "REJECTED",
        "CANCELLED",
        "WITHDRAWN",
    }
