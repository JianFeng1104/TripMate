from tripmate import create_app
from tripmate import environment as environment_module


def _clear_deepseek_environment(monkeypatch):
    for name in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_development_app_loads_project_dotenv(monkeypatch, tmp_path):
    _clear_deepseek_environment(monkeypatch)
    monkeypatch.setattr(environment_module, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=dotenv-test-value\n"
        "DEEPSEEK_MODEL=dotenv-test-model\n",
        encoding="utf-8",
    )

    app = create_app(
        {
            "APP_ENV": "development",
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    assert app.config["DEEPSEEK_API_KEY"] == "dotenv-test-value"
    assert app.config["DEEPSEEK_MODEL"] == "dotenv-test-model"


def test_os_environment_wins_over_dotenv(monkeypatch, tmp_path):
    _clear_deepseek_environment(monkeypatch)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "os-test-value")
    monkeypatch.setattr(environment_module, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=dotenv-test-value\n",
        encoding="utf-8",
    )

    app = create_app(
        {
            "APP_ENV": "development",
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    assert app.config["DEEPSEEK_API_KEY"] == "os-test-value"


def test_missing_dotenv_does_not_prevent_app_startup(monkeypatch, tmp_path):
    _clear_deepseek_environment(monkeypatch)
    monkeypatch.setattr(environment_module, "PROJECT_ROOT", tmp_path)

    app = create_app(
        {
            "APP_ENV": "development",
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    assert app.config["APP_ENV"] == "development"
    assert app.config["DEEPSEEK_API_KEY"] == ""
