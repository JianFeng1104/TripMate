from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    return datetime.now(UTC)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    trips = db.relationship(
        "Trip", back_populates="creator", cascade="all, delete-orphan", lazy="selectin"
    )
    join_requests = db.relationship(
        "JoinRequest",
        back_populates="applicant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Trip(db.Model):
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_trip_date_order"),
        CheckConstraint(
            "expected_companions BETWEEN 1 AND 20", name="ck_trip_expected_companions"
        ),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_trip_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    destination = db.Column(db.String(100), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    style = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    expected_companions = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(10), nullable=False, default="OPEN", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    creator = db.relationship("User", back_populates="trips")
    join_requests = db.relationship(
        "JoinRequest",
        back_populates="trip",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="JoinRequest.created_at.desc()",
    )

    @property
    def accepted_requests(self):
        return [item for item in self.join_requests if item.status == "ACCEPTED"]

    @property
    def remaining_spots(self):
        return max(self.expected_companions - len(self.accepted_requests), 0)


class JoinRequest(db.Model):
    __table_args__ = (
        UniqueConstraint("trip_id", "applicant_id", name="uq_request_trip_applicant"),
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED')", name="ck_request_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False, index=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.String(500), nullable=False, default="")
    status = db.Column(db.String(10), nullable=False, default="PENDING", index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    handled_at = db.Column(db.DateTime(timezone=True))

    trip = db.relationship("Trip", back_populates="join_requests")
    applicant = db.relationship("User", back_populates="join_requests")

