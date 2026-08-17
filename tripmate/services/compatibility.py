"""Deterministic, provider-independent Trip compatibility scoring."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from ..extensions import db
from ..models import Trip


DESTINATION_WEIGHT = 30
DATE_WEIGHT = 30
STYLE_WEIGHT = 20
AVAILABILITY_WEIGHT = 20


@dataclass(frozen=True, slots=True)
class TripSearchCriteria:
    """Normalized preferences used by Trip search and compatibility scoring."""

    destination: str | None = None
    style: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    min_available_spots: int | None = None

    @property
    def has_conditions(self) -> bool:
        """Return whether at least one preference participates in scoring."""

        return any(
            (
                self.destination,
                self.style,
                self.start_date,
                self.end_date,
                self.min_available_spots is not None,
            )
        )

    def to_dict(self) -> dict[str, str | int | bool | None]:
        """Return a JSON-compatible representation of the criteria."""

        return {
            "destination": self.destination,
            "style": self.style,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "min_available_spots": self.min_available_spots,
            "has_conditions": self.has_conditions,
        }


def calculate_trip_compatibility(
    trip_id: int,
    criteria: TripSearchCriteria | Mapping[str, Any],
) -> dict[str, Any]:
    """Calculate a normalized rule-based score for one persisted Trip.

    ``trip_id`` is explicit so a future tool wrapper never needs to receive an
    ORM object. Missing criteria produce ``score=0`` and ``scored=False`` rather
    than inventing a perfect match.
    """

    trip = db.session.get(Trip, trip_id)
    if trip is None:
        raise LookupError(f"Trip {trip_id} does not exist.")
    return _calculate_trip_compatibility(trip, _coerce_criteria(criteria))


def _calculate_trip_compatibility(
    trip: Trip,
    criteria: TripSearchCriteria,
) -> dict[str, Any]:
    component_scores = {
        "destination_score": 0,
        "date_score": 0,
        "style_score": 0,
        "availability_score": 0,
    }
    possible_score = 0
    reasons: list[str] = []

    if criteria.destination:
        possible_score += DESTINATION_WEIGHT
        if criteria.destination.casefold() in trip.destination.casefold():
            component_scores["destination_score"] = DESTINATION_WEIGHT
            reasons.append(f"目的地与 {trip.destination} 匹配")

    if criteria.start_date or criteria.end_date:
        possible_score += DATE_WEIGHT
        preferred_start = criteria.start_date or date.min
        preferred_end = criteria.end_date or date.max
        if trip.start_date <= preferred_end and trip.end_date >= preferred_start:
            component_scores["date_score"] = DATE_WEIGHT
            reasons.append("旅行日期与你的目标日期存在重叠")

    if criteria.style:
        possible_score += STYLE_WEIGHT
        if trip.style == criteria.style:
            component_scores["style_score"] = STYLE_WEIGHT
            reasons.append(f"旅行风格与“{trip.style}”一致")

    if criteria.min_available_spots is not None:
        possible_score += AVAILABILITY_WEIGHT
        if trip.remaining_spots >= criteria.min_available_spots:
            component_scores["availability_score"] = AVAILABILITY_WEIGHT
            reasons.append(f"当前仍有 {trip.remaining_spots} 个同行名额")

    earned_score = sum(component_scores.values())
    score = round(earned_score / possible_score * 100) if possible_score else 0
    score = max(0, min(score, 100))
    return {
        "score": score,
        **component_scores,
        "earned_score": earned_score,
        "possible_score": possible_score,
        "remaining_spots": trip.remaining_spots,
        "scored": possible_score > 0,
        "reasons": reasons,
    }


def _coerce_criteria(
    criteria: TripSearchCriteria | Mapping[str, Any],
) -> TripSearchCriteria:
    if isinstance(criteria, TripSearchCriteria):
        return criteria
    if not isinstance(criteria, Mapping):
        raise TypeError("criteria must be TripSearchCriteria or a mapping")
    return TripSearchCriteria(
        destination=_optional_text(criteria.get("destination")),
        style=_optional_text(criteria.get("style")),
        start_date=_optional_date(criteria.get("start_date"), "start_date"),
        end_date=_optional_date(criteria.get("end_date"), "end_date"),
        min_available_spots=_optional_int(
            criteria.get("min_available_spots"), "min_available_spots"
        ),
    )


def _optional_text(value: Any) -> str | None:
    cleaned = " ".join(str(value).split()) if value is not None else ""
    return cleaned or None


def _optional_date(value: Any, field_name: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format") from error


def _optional_int(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error
