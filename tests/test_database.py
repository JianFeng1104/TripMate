import sqlite3

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from tripmate import create_app
from tripmate.extensions import db
from tripmate.models import JoinRequest


def test_sqlite_foreign_keys_are_enabled(app):
    with app.app_context():
        assert db.session.scalar(text("PRAGMA foreign_keys")) == 1


def test_invalid_foreign_key_is_rejected(app):
    with app.app_context():
        db.session.add(
            JoinRequest(
                trip_id=999_999,
                applicant_id=999_999,
                message="invalid foreign key",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert db.session.scalar(select(db.func.count(JoinRequest.id))) == 0


def test_legacy_baseline_upgrade_preserves_join_request_data(tmp_path):
    database_path = tmp_path / "legacy-tripmate.db"
    legacy_app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        }
    )
    runner = legacy_app.test_cli_runner()
    baseline = runner.invoke(args=["db", "upgrade", "tm_20260815_baseline"])
    assert baseline.exit_code == 0, baseline.output

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(
            """
            INSERT INTO user VALUES
                (1, 'owner', 'owner@example.com', 'hash', '', '2026-01-01 00:00:00'),
                (2, 'guest', 'guest@example.com', 'hash', '', '2026-01-01 00:00:00');
            INSERT INTO trip VALUES
                (1, 1, 'Legacy Trip', '2026-01-01', '2026-01-02', '其他',
                 'legacy data', 1, 'OPEN', '2026-01-01 00:00:00');
            INSERT INTO join_request VALUES
                (1, 1, 2, 'legacy request', 'PENDING', '2026-01-01 00:00:00', NULL);
            """
        )

    upgraded = runner.invoke(args=["db", "upgrade"])
    assert upgraded.exit_code == 0, upgraded.output
    with legacy_app.app_context():
        table_sql = db.session.scalar(
            text("SELECT sql FROM sqlite_master WHERE name = 'join_request'")
        )
        request_item = db.session.get(JoinRequest, 1)
        assert "CANCELLED" in table_sql
        assert request_item.status == "PENDING"
        assert request_item.message == "legacy request"
        assert db.session.scalar(text("SELECT version_num FROM alembic_version")) == (
            "tm_20260815_lifecycle"
        )
        assert db.session.scalar(text("PRAGMA foreign_keys")) == 1
