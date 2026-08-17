"""Allow cancelled join requests

Revision ID: tm_20260815_cancelled
Revises: tm_20260815_baseline
Create Date: 2026-08-15 15:38:47.307257

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'tm_20260815_cancelled'
down_revision = 'tm_20260815_baseline'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("join_request", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_request_status", type_="check")
        batch_op.create_check_constraint(
            "ck_request_status",
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
        )


def downgrade():
    with op.batch_alter_table("join_request", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_request_status", type_="check")
        batch_op.create_check_constraint(
            "ck_request_status",
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED')",
        )
