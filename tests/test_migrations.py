from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from tripmate import create_app
from tripmate.extensions import db


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
HEAD_REVISION = "tm_20260815_lifecycle"


def test_migration_repository_has_expected_head():
    config = Config(str(MIGRATIONS_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == [HEAD_REVISION]
    assert scripts.get_revision(HEAD_REVISION).down_revision == "tm_20260815_cancelled"


def test_empty_database_upgrade_creates_current_schema(tmp_path):
    database_path = tmp_path / "empty-tripmate.db"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        }
    )

    with app.app_context():
        assert inspect(db.engine).get_table_names() == []

    result = app.test_cli_runner().invoke(args=["db", "upgrade"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        inspector = inspect(db.engine)
        assert {"user", "trip", "join_request", "alembic_version"} <= set(
            inspector.get_table_names()
        )
        request_checks = {
            item["name"]: item["sqltext"]
            for item in inspector.get_check_constraints("join_request")
        }
        request_uniques = {
            item["name"]: tuple(item["column_names"])
            for item in inspector.get_unique_constraints("join_request")
        }
        request_foreign_keys = {
            (tuple(item["constrained_columns"]), item["referred_table"])
            for item in inspector.get_foreign_keys("join_request")
        }
        trip_checks = {
            item["name"]: item["sqltext"]
            for item in inspector.get_check_constraints("trip")
        }

        assert "CANCELLED" in request_checks["ck_request_status"]
        assert "WITHDRAWN" in request_checks["ck_request_status"]
        assert "CANCELLED" in trip_checks["ck_trip_status"]
        assert request_uniques["uq_request_trip_applicant"] == (
            "trip_id",
            "applicant_id",
        )
        assert request_foreign_keys == {
            (("trip_id",), "trip"),
            (("applicant_id",), "user"),
        }
        assert db.session.scalar(text("PRAGMA foreign_keys")) == 1
        assert db.session.scalar(text("SELECT version_num FROM alembic_version")) == (
            HEAD_REVISION
        )


def test_lifecycle_migration_preserves_existing_status_data(tmp_path):
    database_path = tmp_path / "tripmate-before-lifecycle.db"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        }
    )
    runner = app.test_cli_runner()
    previous = runner.invoke(args=["db", "upgrade", "tm_20260815_cancelled"])
    assert previous.exit_code == 0, previous.output

    with app.app_context():
        db.session.execute(
            text(
                """
                INSERT INTO user (id, username, email, password_hash, bio, created_at) VALUES
                    (1, 'owner', 'owner@example.com', 'hash', '', '2026-01-01'),
                    (2, 'guest1', 'guest1@example.com', 'hash', '', '2026-01-01'),
                    (3, 'guest2', 'guest2@example.com', 'hash', '', '2026-01-01'),
                    (4, 'guest3', 'guest3@example.com', 'hash', '', '2026-01-01'),
                    (5, 'guest4', 'guest4@example.com', 'hash', '', '2026-01-01')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO trip
                    (id, creator_id, destination, start_date, end_date, style, description,
                     expected_companions, status, created_at)
                VALUES
                    (1, 1, 'Open Trip', '2026-09-01', '2026-09-02', '其他',
                     'open trip data', 4, 'OPEN', '2026-01-01'),
                    (2, 1, 'Closed Trip', '2026-10-01', '2026-10-02', '其他',
                     'closed trip data', 1, 'CLOSED', '2026-01-01')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO join_request
                    (id, trip_id, applicant_id, message, status, created_at, handled_at)
                VALUES
                    (1, 1, 2, '', 'PENDING', '2026-01-01', NULL),
                    (2, 1, 3, '', 'ACCEPTED', '2026-01-01', '2026-01-02'),
                    (3, 1, 4, '', 'REJECTED', '2026-01-01', '2026-01-02'),
                    (4, 1, 5, '', 'CANCELLED', '2026-01-01', '2026-01-02')
                """
            )
        )
        db.session.commit()

    upgraded = runner.invoke(args=["db", "upgrade"])
    assert upgraded.exit_code == 0, upgraded.output
    with app.app_context():
        assert db.session.execute(
            text("SELECT id, status FROM trip ORDER BY id")
        ).all() == [(1, "OPEN"), (2, "CLOSED")]
        assert db.session.execute(
            text("SELECT id, status FROM join_request ORDER BY id")
        ).all() == [
            (1, "PENDING"),
            (2, "ACCEPTED"),
            (3, "REJECTED"),
            (4, "CANCELLED"),
        ]
        assert db.session.scalar(text("SELECT version_num FROM alembic_version")) == (
            HEAD_REVISION
        )
