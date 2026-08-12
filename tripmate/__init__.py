import os
from pathlib import Path

from flask import Flask, render_template

from .extensions import db
from .utils import csrf_token


def create_app(test_config=None):
    """Create and configure the TripMate application."""
    app = Flask(__name__, instance_relative_config=True)
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("TRIPMATE_SECRET_KEY", "tripmate-local-development-key"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{instance_path / 'tripmate.db'}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    app.jinja_env.globals["csrf_token"] = csrf_token

    from . import models  # noqa: F401
    from .auth import bp as auth_bp
    from .main import bp as main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    from .commands import seed_demo

    app.cli.add_command(seed_demo)

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

    with app.app_context():
        db.create_all()

    return app
