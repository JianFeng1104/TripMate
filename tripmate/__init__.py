import logging
import mimetypes
from pathlib import Path

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import configure_app
from .extensions import db, migrate
from .utils import csrf_token


def create_app(test_config=None):
    """Create and configure the TripMate application."""
    # Windows can register .js as text/plain.  With the nosniff security header,
    # browsers then refuse to execute the script and reveal animations stay hidden.
    mimetypes.add_type("application/javascript", ".js")
    app = Flask(__name__, instance_relative_config=True)
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    configure_app(app, instance_path, test_config)
    app.logger.setLevel(getattr(logging, app.config["LOG_LEVEL"], logging.INFO))
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1
        )

    db.init_app(app)
    migrate.init_app(app, db)
    app.jinja_env.globals["csrf_token"] = csrf_token

    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .agent.routes import bp as agent_bp
    from .main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(main_bp)

    from .commands import seed_demo

    app.cli.add_command(seed_demo)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "TripMate"}

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html", error=error), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html", error=error), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html", error=error), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template("errors/413.html", error=error), 413

    @app.errorhandler(500)
    def internal_server_error(error):
        original = getattr(error, "original_exception", None)
        app.logger.error(
            "unexpected_exception service=TripMate category=%s",
            type(original or error).__name__,
        )
        return render_template("errors/500.html"), 500

    app.logger.info(
        "application_start service=TripMate environment=%s",
        app.config["APP_ENV"],
    )

    return app
