"""Advanced Trip discovery backed by deterministic business rules."""

from datetime import date
from typing import Any

from sqlalchemy import select

from ..extensions import db
from ..models import Trip
from .compatibility import (
    TripSearchCriteria,
    _calculate_trip_compatibility,
    _coerce_criteria,
)
from .trip_service import _serialize_trip


TRAVEL_STYLES = (
    "城市探索",
    "自然户外",
    "美食体验",
    "摄影打卡",
    "文化历史",
    "轻松度假",
    "其他",
)


def search_trips(
    destination: str | None = None,
    style: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    min_available_spots: int | str | None = None,
    page: int = 1,
    per_page: int = 9,
    strict_filters: bool = True,
) -> dict[str, Any]:
    """Search OPEN Trips and return safe DTOs plus pagination metadata.

    By default all supplied criteria are deterministic filters. A future tool
    may pass ``strict_filters=False`` to rank all OPEN Trips as preferences
    without excluding partial matches. Ties use descending Trip id.
    """

    criteria = _coerce_criteria(
        {
            "destination": destination,
            "style": style,
            "start_date": start_date,
            "end_date": end_date,
            "min_available_spots": min_available_spots,
        }
    )
    _validate_criteria(criteria)
    page = max(_positive_int(page, "page"), 1)
    per_page = _positive_int(per_page, "per_page")
    if per_page > 100:
        raise ValueError("per_page cannot exceed 100")

    statement = select(Trip).where(Trip.status == "OPEN")
    if strict_filters and criteria.destination:
        statement = statement.where(Trip.destination.ilike(f"%{criteria.destination}%"))
    if strict_filters and criteria.style:
        statement = statement.where(Trip.style == criteria.style)
    if strict_filters and criteria.start_date:
        statement = statement.where(Trip.end_date >= criteria.start_date)
    if strict_filters and criteria.end_date:
        statement = statement.where(Trip.start_date <= criteria.end_date)

    trips = db.session.scalars(
        statement.order_by(Trip.start_date.asc(), Trip.created_at.desc(), Trip.id.desc())
    ).all()
    if strict_filters and criteria.min_available_spots is not None:
        trips = [
            trip for trip in trips if trip.remaining_spots >= criteria.min_available_spots
        ]

    ranked: list[tuple[Trip, dict[str, Any]]] = [
        (trip, _calculate_trip_compatibility(trip, criteria)) for trip in trips
    ]
    if criteria.has_conditions:
        ranked.sort(key=lambda item: (-item[1]["score"], -item[0].id))

    total = len(ranked)
    pages = (total + per_page - 1) // per_page
    current_page = min(page, pages) if pages else 1
    start = (current_page - 1) * per_page
    items = []
    for trip, compatibility in ranked[start : start + per_page]:
        item = _serialize_trip(trip, include_description=True)
        item["compatibility"] = compatibility if criteria.has_conditions else None
        items.append(item)

    return {
        "criteria": criteria.to_dict(),
        "strict_filters": strict_filters,
        "items": items,
        "pagination": {
            "page": current_page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_prev": current_page > 1,
            "has_next": current_page < pages,
            "prev_num": current_page - 1 if current_page > 1 else None,
            "next_num": current_page + 1 if current_page < pages else None,
        },
    }


def _validate_criteria(criteria: TripSearchCriteria) -> None:
    if criteria.style and criteria.style not in TRAVEL_STYLES:
        raise ValueError("style is not in the TripMate travel-style catalog")
    if criteria.start_date and criteria.end_date and criteria.end_date < criteria.start_date:
        raise ValueError("end_date cannot be earlier than start_date")
    if criteria.min_available_spots is not None and not 0 <= criteria.min_available_spots <= 20:
        raise ValueError("min_available_spots must be between 0 and 20")


def _positive_int(value: Any, field_name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error
    if result < 1:
        return 1
    return result
