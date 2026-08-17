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


def upgrade():
    with op.get_context().autocommit_block():
        connection = op.get_bind()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        try:
            with op.batch_alter_table("trip", recreate="always") as batch_op:
                batch_op.drop_constraint("ck_trip_status", type_="check")
                batch_op.create_check_constraint(
                    "ck_trip_status",
                    "status IN ('OPEN', 'CLOSED', 'CANCELLED')",
                )

            with op.batch_alter_table("join_request", recreate="always") as batch_op:
                batch_op.drop_constraint("ck_request_status", type_="check")
                batch_op.create_check_constraint(
                    "ck_request_status",
                    "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED', 'WITHDRAWN')",
                )
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"Foreign key violations after migration: {violations}")
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade():
    with op.get_context().autocommit_block():
        connection = op.get_bind()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        try:
            with op.batch_alter_table("join_request", recreate="always") as batch_op:
                batch_op.drop_constraint("ck_request_status", type_="check")
                batch_op.create_check_constraint(
                    "ck_request_status",
                    "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
                )

            with op.batch_alter_table("trip", recreate="always") as batch_op:
                batch_op.drop_constraint("ck_trip_status", type_="check")
                batch_op.create_check_constraint(
                    "ck_trip_status",
                    "status IN ('OPEN', 'CLOSED')",
                )
            violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"Foreign key violations after downgrade: {violations}")
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
