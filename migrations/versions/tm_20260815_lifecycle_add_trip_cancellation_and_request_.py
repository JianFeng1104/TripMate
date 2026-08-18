"""Add trip cancellation and request withdrawal states

Revision ID: tm_20260815_lifecycle
Revises: tm_20260815_cancelled
Create Date: 2026-08-15 16:08:07.241436

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'tm_20260815_lifecycle'
down_revision = 'tm_20260815_cancelled'
branch_labels = None
depends_on = None


def _replace_check_constraint(table_name, constraint_name, condition):
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table_name, recreate="always") as batch_op:
            batch_op.drop_constraint(constraint_name, type_="check")
            batch_op.create_check_constraint(constraint_name, condition)
        return

    op.drop_constraint(constraint_name, table_name, type_="check")
    op.create_check_constraint(constraint_name, table_name, condition)


def _upgrade_constraints():
    _replace_check_constraint(
        "trip",
        "ck_trip_status",
        "status IN ('OPEN', 'CLOSED', 'CANCELLED')",
    )
    _replace_check_constraint(
        "join_request",
        "ck_request_status",
        "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'WITHDRAWN')",
    )


def _downgrade_constraints():
    _replace_check_constraint(
        "join_request",
        "ck_request_status",
        "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
    )
    _replace_check_constraint(
        "trip",
        "ck_trip_status",
        "status IN ('OPEN', 'CLOSED')",
    )


def _run_with_sqlite_foreign_keys_disabled(operation, check_label):
    connection = op.get_bind()
    with op.get_context().autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        try:
            operation()
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(
                    f"Foreign key violations after {check_label}: {violations}"
                )
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        _run_with_sqlite_foreign_keys_disabled(_upgrade_constraints, "migration")
        return
    _upgrade_constraints()


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        _run_with_sqlite_foreign_keys_disabled(_downgrade_constraints, "downgrade")
        return
    _downgrade_constraints()
