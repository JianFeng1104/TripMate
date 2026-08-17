"""Reusable TripMate business services.

The functions exported here are independent of Flask request handling and can
be reused by the current web UI or by a future tool adapter.
"""

from .compatibility import TripSearchCriteria, calculate_trip_compatibility
from .trip_search import TRAVEL_STYLES, search_trips
from .trip_service import get_public_trip_details, get_public_user_profile

__all__ = [
    "TRAVEL_STYLES",
    "TripSearchCriteria",
    "calculate_trip_compatibility",
    "get_public_trip_details",
    "get_public_user_profile",
    "search_trips",
]
