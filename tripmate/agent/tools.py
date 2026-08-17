"""TripMate read-only tool schemas and explicit service wrappers."""

import json
import logging
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from ..services import (
    TRAVEL_STYLES,
    calculate_trip_compatibility,
    get_public_trip_details,
    get_public_user_profile,
    search_trips,
)


LOGGER = logging.getLogger(__name__)


FORBIDDEN_OUTPUT_KEYS = {
    "api_key",
    "authorization",
    "authorization_header",
    "email",
    "password",
    "password_hash",
    "session",
    "secret_key",
    "csrf",
    "csrf_token",
    "_csrf_token",
}

STYLE_PARAMETER = {
    "type": "string",
    "enum": list(TRAVEL_STYLES),
    "description": (
        "Convert the user's natural-language preference to exactly one canonical "
        "TripMate style value from this enum; for example, photography maps to 摄影打卡."
    ),
}

TRIP_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_trips",
            "description": "Search real OPEN TripMate trips using deterministic filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {"type": "string"},
                    "style": STYLE_PARAMETER,
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Preferred start date in YYYY-MM-DD format.",
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Preferred end date in YYYY-MM-DD format.",
                    },
                    "min_available_spots": {"type": "integer", "minimum": 0, "maximum": 20},
                    "page": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trip_details",
            "description": "Get the safe public details of one real TripMate trip.",
            "parameters": {
                "type": "object",
                "properties": {"trip_id": {"type": "integer", "minimum": 1}},
                "required": ["trip_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_trip_compatibility",
            "description": "Calculate TripMate's deterministic compatibility score for one trip.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trip_id": {"type": "integer", "minimum": 1},
                    "destination": {"type": "string"},
                    "style": STYLE_PARAMETER,
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Preferred start date in YYYY-MM-DD format.",
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Preferred end date in YYYY-MM-DD format.",
                    },
                    "min_available_spots": {"type": "integer", "minimum": 0, "maximum": 20},
                },
                "required": ["trip_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_creator_profile",
            "description": "Get a TripMate creator's safe public profile.",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "integer", "minimum": 1}},
                "required": ["user_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _search_trips(arguments: dict[str, Any], trusted_context: Mapping[str, Any]) -> Any:
    _reject_unknown_arguments(
        arguments,
        {"destination", "style", "start_date", "end_date", "min_available_spots", "page"},
    )
    _validate_optional_strings(arguments, {"destination"})
    _validate_optional_enum(arguments, "style", TRAVEL_STYLES)
    _validate_optional_dates(arguments)
    _validate_optional_int(arguments, "min_available_spots", minimum=0, maximum=20)
    _validate_optional_int(arguments, "page", minimum=1)
    return search_trips(**arguments, per_page=5)


def _get_trip_details(arguments: dict[str, Any], trusted_context: Mapping[str, Any]) -> Any:
    _reject_unknown_arguments(arguments, {"trip_id"})
    trip_id = _required_int(arguments, "trip_id", minimum=1)
    return get_public_trip_details(trip_id)


def _calculate_compatibility(arguments: dict[str, Any], trusted_context: Mapping[str, Any]) -> Any:
    _reject_unknown_arguments(
        arguments,
        {"trip_id", "destination", "style", "start_date", "end_date", "min_available_spots"},
    )
    trip_id = _required_int(arguments, "trip_id", minimum=1)
    criteria = {key: value for key, value in arguments.items() if key != "trip_id"}
    _validate_optional_strings(criteria, {"destination"})
    _validate_optional_enum(criteria, "style", TRAVEL_STYLES)
    _validate_optional_dates(criteria)
    _validate_optional_int(criteria, "min_available_spots", minimum=0, maximum=20)
    return calculate_trip_compatibility(trip_id, criteria)


def _get_creator_profile(arguments: dict[str, Any], trusted_context: Mapping[str, Any]) -> Any:
    _reject_unknown_arguments(arguments, {"user_id"})
    user_id = _required_int(arguments, "user_id", minimum=1)
    return get_public_user_profile(user_id)


TOOL_HANDLERS: dict[str, Callable[[dict[str, Any], Mapping[str, Any]], Any]] = {
    "search_trips": _search_trips,
    "get_trip_details": _get_trip_details,
    "calculate_trip_compatibility": _calculate_compatibility,
    "get_creator_profile": _get_creator_profile,
}


def execute_tool_call(
    tool_name: str,
    raw_arguments: str,
    trusted_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and execute one explicitly allow-listed read-only tool."""

    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        LOGGER.warning("agent_tool service=TripMate tool=%s success=false category=unknown", tool_name)
        return _tool_error("unknown_tool", "This tool is not available.")
    try:
        arguments = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        LOGGER.warning(
            "agent_tool service=TripMate tool=%s success=false category=invalid_json",
            tool_name,
        )
        return _tool_error("invalid_arguments", "Tool arguments must be valid JSON.")
    if not isinstance(arguments, dict):
        LOGGER.warning(
            "agent_tool service=TripMate tool=%s success=false category=invalid_type",
            tool_name,
        )
        return _tool_error("invalid_arguments", "Tool arguments must be a JSON object.")
    try:
        result = handler(arguments, trusted_context or {})
        safe_result = _sanitize_output(result)
        json.dumps(safe_result, ensure_ascii=False)
        LOGGER.info("agent_tool service=TripMate tool=%s success=true", tool_name)
        return {"ok": True, "data": safe_result}
    except (LookupError, TypeError, ValueError) as error:
        LOGGER.warning(
            "agent_tool service=TripMate tool=%s success=false category=%s",
            tool_name,
            type(error).__name__,
        )
        return _tool_error("service_error", _safe_service_message(error))
    except Exception as error:
        LOGGER.error(
            "agent_tool service=TripMate tool=%s success=false category=%s",
            tool_name,
            type(error).__name__,
        )
        return _tool_error("tool_failed", "The tool could not complete safely.")


def _sanitize_output(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize_output(item)
            for key, item in value.items()
            if str(key).casefold() not in FORBIDDEN_OUTPUT_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_output(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("Tool result is not JSON-compatible")


def _reject_unknown_arguments(arguments: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = set(arguments) - allowed
    if unknown:
        raise ValueError("Unsupported tool arguments were provided.")


def _required_int(arguments: Mapping[str, Any], key: str, minimum: int) -> int:
    if key not in arguments or isinstance(arguments[key], bool) or not isinstance(arguments[key], int):
        raise ValueError(f"{key} must be an integer.")
    if arguments[key] < minimum:
        raise ValueError(f"{key} is outside the allowed range.")
    return arguments[key]


def _validate_optional_int(
    arguments: Mapping[str, Any], key: str, minimum: int, maximum: int | None = None
) -> None:
    if key not in arguments:
        return
    value = arguments[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer.")
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{key} is outside the allowed range.")


def _validate_optional_strings(arguments: Mapping[str, Any], keys: set[str]) -> None:
    for key in keys & set(arguments):
        value = arguments[key]
        if not isinstance(value, str) or len(value) > 100:
            raise ValueError(f"{key} must be a short string.")


def _validate_optional_enum(
    arguments: Mapping[str, Any], key: str, allowed_values: tuple[str, ...]
) -> None:
    if key not in arguments:
        return
    value = arguments[key]
    if not isinstance(value, str) or value not in allowed_values:
        raise ValueError(f"{key} must use a canonical application value.")


def _validate_optional_dates(arguments: Mapping[str, Any]) -> None:
    parsed_dates: dict[str, date] = {}
    for key in ("start_date", "end_date"):
        if key not in arguments:
            continue
        value = arguments[key]
        if not isinstance(value, str):
            raise ValueError(f"{key} must use YYYY-MM-DD format.")
        try:
            parsed_dates[key] = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError(f"{key} must use YYYY-MM-DD format.") from error
    if (
        "start_date" in parsed_dates
        and "end_date" in parsed_dates
        and parsed_dates["end_date"] < parsed_dates["start_date"]
    ):
        raise ValueError("end_date cannot be earlier than start_date.")


def _tool_error(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _safe_service_message(error: Exception) -> str:
    if isinstance(error, LookupError):
        return "The requested record was not found."
    return "The requested parameters are invalid."
