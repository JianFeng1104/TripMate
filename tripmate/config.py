"""Small environment-aware configuration layer for TripMate."""

import os
from pathlib import Path
from typing import Any

from .environment import load_local_environment


DEVELOPMENT_SECRET = "tripmate-local-development-key"


class BaseConfig:
    DEBUG = False
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024
    SESSION_COOKIE_NAME = "tripmate_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    DEEPSEEK_TIMEOUT = 25
    TRUST_PROXY = False
    LOG_LEVEL = "INFO"


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True


class ProductionConfig(BaseConfig):
    APP_ENV = "production"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


class DemoConfig(ProductionConfig):
    """Production security with explicit portfolio demo seeding enabled."""

    APP_ENV = "demo"


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "demo": DemoConfig,
    "portfolio": DemoConfig,
}


def configure_app(app, instance_path: Path, overrides: dict[str, Any] | None = None) -> None:
    """Load one config layer, environment values, then explicit test overrides."""

    overrides = overrides or {}
    requested_env = overrides.get("APP_ENV")
    if not requested_env and overrides.get("TESTING"):
        requested_env = "testing"
    bootstrap_environment = str(
        requested_env
        or os.environ.get("TRIPMATE_ENV")
        or os.environ.get("APP_ENV")
        or "development"
    ).lower()
    load_local_environment(environment=bootstrap_environment)
    environment = str(
        requested_env
        or os.environ.get("TRIPMATE_ENV")
        or os.environ.get("APP_ENV")
        or "development"
    ).lower()
    config_class = CONFIGS.get(environment)
    if config_class is None:
        raise RuntimeError(f"Unsupported TripMate environment: {environment}")

    app.config.from_object(config_class)
    secret_key = os.environ.get("TRIPMATE_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not secret_key and not issubclass(config_class, ProductionConfig):
        secret_key = DEVELOPMENT_SECRET if environment == "development" else "test-secret"
    database_uri = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("TRIPMATE_DATABASE_URI")
        or f"sqlite:///{instance_path / 'tripmate.db'}"
    )
    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI=_normalize_database_url(database_uri),
        DEEPSEEK_API_KEY=os.environ.get("DEEPSEEK_API_KEY", ""),
        DEEPSEEK_BASE_URL=os.environ.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ),
        DEEPSEEK_MODEL=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        TRUST_PROXY=_environment_flag("TRIPMATE_TRUST_PROXY"),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO").upper(),
    )
    app.config.update(overrides)
    if app.config.get("APP_ENV") in {"production", "demo"}:
        app.config.update(DEBUG=False, TESTING=False, SESSION_COOKIE_SECURE=True)
    _validate_secure_config(app.config)


def _validate_secure_config(config: dict[str, Any]) -> None:
    if config.get("APP_ENV") not in {"production", "demo"}:
        return
    secret_key = str(config.get("SECRET_KEY") or "").strip()
    if not secret_key or secret_key in {
        DEVELOPMENT_SECRET,
        "replace-me",
        "replace-with-local-secret",
    }:
        raise RuntimeError("SECRET_KEY must be configured in production or demo.")


def _normalize_database_url(database_url: str) -> str:
    """Select the installed psycopg 3 dialect for Railway PostgreSQL URLs."""

    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _environment_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
