import json
from pathlib import Path

import psycopg

from tripmate import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_psycopg_driver_is_importable():
    assert psycopg.__version__


def test_railway_postgresql_url_selects_psycopg_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/tripmate_test")

    app = create_app(
        {
            "APP_ENV": "testing",
            "SECRET_KEY": "test-secret",
            "DEEPSEEK_API_KEY": "",
        }
    )

    assert app.config["SQLALCHEMY_DATABASE_URI"] == (
        "postgresql+psycopg://localhost/tripmate_test"
    )


def test_postgresql_migration_history_renders_offline(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/tripmate_migration_test")
    app = create_app(
        {
            "APP_ENV": "testing",
            "SECRET_KEY": "test-secret",
            "DEEPSEEK_API_KEY": "",
        }
    )

    result = app.test_cli_runner().invoke(args=["db", "upgrade", "--sql"])

    assert result.exit_code == 0, result.output
    assert "CREATE TABLE" in result.output
    assert "tm_20260815_lifecycle" in result.output
    assert "PRAGMA" not in result.output


def test_railway_config_is_safe_and_uses_required_commands():
    raw_config = (PROJECT_ROOT / "railway.json").read_text(encoding="utf-8")
    config = json.loads(raw_config)
    deploy = config["deploy"]

    assert config["$schema"] == "https://railway.com/railway.schema.json"
    assert deploy["preDeployCommand"] == (
        "python -m flask --app run:app db upgrade"
    )
    assert deploy["startCommand"] == (
        "gunicorn --bind 0.0.0.0:$PORT --workers 2 wsgi:app"
    )
    assert deploy["healthcheckPath"] == "/health"
    assert deploy["healthcheckTimeout"] > 0
    assert deploy["restartPolicyType"] == "ON_FAILURE"
    for forbidden_name in (
        "SECRET_KEY",
        "TRIPMATE_SECRET_KEY",
        "DEEPSEEK_API_KEY",
        "DATABASE_URL",
    ):
        assert forbidden_name not in raw_config
