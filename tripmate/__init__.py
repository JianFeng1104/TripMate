from pathlib import Path

from flask import Flask, render_template

from .extensions import db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY="tripmate-local-development-key",
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{instance_path / 'tripmate.db'}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    with app.app_context():
        db.create_all()

    return app

