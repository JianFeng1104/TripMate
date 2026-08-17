"""Safe public-data services for TripMate resources."""

from typing import Any

from ..extensions import db
from ..models import Trip, User


def get_public_trip_details(trip_id: int) -> dict[str, Any]:
    """Return public Trip details without private creator credentials."""

    trip = db.session.get(Trip, trip_id)
    if trip is None:
        raise LookupError(f"Trip {trip_id} does not exist.")
    return _serialize_trip(trip, include_description=True)


def get_public_user_profile(user_id: int) -> dict[str, Any]:
    """Return only the public fields that currently exist on a TripMate user."""

    user = db.session.get(User, user_id)
    if user is None:
        raise LookupError(f"User {user_id} does not exist.")
    return _serialize_user(user)


def _serialize_trip(trip: Trip, *, include_description: bool) -> dict[str, Any]:
    """Convert a Trip ORM entity into a stable, JSON-compatible DTO."""

    result: dict[str, Any] = {
        "trip_id": trip.id,
        "destination": trip.destination,
        "start_date": trip.start_date.isoformat(),
        "end_date": trip.end_date.isoformat(),
        "style": trip.style,
        "expected_companions": trip.expected_companions,
        "accepted_count": len(trip.accepted_requests),
        "remaining_spots": trip.remaining_spots,
        "status": trip.status,
        "creator": _serialize_user(trip.creator),
    }
    if include_description:
        result["description"] = trip.description
    return result


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "username": user.username,
        "bio": user.bio,
    }
