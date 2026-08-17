"""TripMate legacy schema baseline

Revision ID: tm_20260815_baseline
Revises:
Create Date: 2026-08-15 15:38:46.737236

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'tm_20260815_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("bio", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_username", "user", ["username"], unique=True)

    op.create_table(
        "trip",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("destination", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("style", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("expected_companions", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_trip_date_order"),
        sa.CheckConstraint(
            "expected_companions BETWEEN 1 AND 20",
            name="ck_trip_expected_companions",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED')",
            name="ck_trip_status",
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_creator_id", "trip", ["creator_id"], unique=False)
    op.create_index("ix_trip_destination", "trip", ["destination"], unique=False)
    op.create_index("ix_trip_status", "trip", ["status"], unique=False)

    op.create_table(
        "join_request",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED')",
            name="ck_request_status",
        ),
        sa.ForeignKeyConstraint(["applicant_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trip.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trip_id",
            "applicant_id",
            name="uq_request_trip_applicant",
        ),
    )
    op.create_index(
        "ix_join_request_applicant_id",
        "join_request",
        ["applicant_id"],
        unique=False,
    )
    op.create_index(
        "ix_join_request_status", "join_request", ["status"], unique=False
    )
    op.create_index(
        "ix_join_request_trip_id", "join_request", ["trip_id"], unique=False
    )


def downgrade():
    op.drop_index("ix_join_request_trip_id", table_name="join_request")
    op.drop_index("ix_join_request_status", table_name="join_request")
    op.drop_index("ix_join_request_applicant_id", table_name="join_request")
    op.drop_table("join_request")
    op.drop_index("ix_trip_status", table_name="trip")
    op.drop_index("ix_trip_destination", table_name="trip")
    op.drop_index("ix_trip_creator_id", table_name="trip")
    op.drop_table("trip")
    op.drop_index("ix_user_username", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
