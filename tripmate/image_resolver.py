"""Presentation-only destination imagery with safe local fallbacks.

The resolver never reads or writes Trip records. A bundled city photo is used
only when it actually represents the requested destination. Other destinations
use a bounded Unsplash lookup when configured, then fall back to one explicitly
generic travel image. Results and attribution metadata share a six-hour cache.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any
from urllib.parse import quote_plus, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_CACHE_LOCK = threading.Lock()

_GENERIC_FALLBACK_IMAGE = "/static/img/travel-fallback.jpg"
_UNSPLASH_HOME_URL = (
    "https://unsplash.com/?utm_source=tripmate&utm_medium=referral"
)

_BUNDLED_DESTINATIONS = (
    (("tokyo", "东京"), "Japan", "/static/img/tokyo-night.jpg"),
    (("penang", "槟城"), "Malaysia", "/static/img/penang-waterfront.jpg"),
    (("dali", "大理"), "China", "/static/img/dali-lake.jpg"),
)

_COUNTRY_HINTS = (
    (("tokyo", "东京", "japan", "日本"), "Japan"),
    (("penang", "槟城", "malaysia", "马来西亚"), "Malaysia"),
    (("dali", "大理", "china", "中国"), "China"),
    (("london", "伦敦", "united kingdom", "英国"), "United Kingdom"),
    (("paris", "巴黎", "france", "法国"), "France"),
    (("seoul", "首尔", "south korea", "韩国"), "South Korea"),
    (("singapore", "新加坡"), "Singapore"),
)


def get_destination_visual(destination: str) -> dict[str, str]:
    """Return safe image and attribution metadata for a destination.

    The return value contains only presentation data and is safe to pass to a
    Jinja template. Provider failures are deliberately swallowed so a network
    outage cannot break Trip discovery.
    """

    normalized = " ".join((destination or "").strip().lower().split())
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(normalized)
        if cached and cached[0] > now:
            return dict(cached[1])

    bundled = _bundled_visual(normalized)
    resolved = bundled or _generic_visual(normalized)
    if not bundled and normalized:
        access_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
        if access_key:
            unsplash = _search_unsplash(normalized, access_key)
            if unsplash:
                resolved.update(unsplash)

    with _CACHE_LOCK:
        _CACHE[normalized] = (now + _CACHE_TTL_SECONDS, resolved)
    return dict(resolved)


def get_destination_image(destination: str) -> str:
    """Return only the image URL for callers that do not need label metadata."""

    return get_destination_visual(destination)["url"]


def clear_destination_image_cache() -> None:
    """Clear the in-memory cache for isolated tests and local development."""

    with _CACHE_LOCK:
        _CACHE.clear()


def _bundled_visual(normalized: str) -> dict[str, str] | None:
    for keywords, country, image_url in _BUNDLED_DESTINATIONS:
        if any(keyword in normalized for keyword in keywords):
            return _local_visual(image_url, country)
    return None


def _generic_visual(normalized: str) -> dict[str, str]:
    country = "Global"
    for keywords, country_label in _COUNTRY_HINTS:
        if any(keyword in normalized for keyword in keywords):
            country = country_label
            break
    return _local_visual(_GENERIC_FALLBACK_IMAGE, country)


def _local_visual(image_url: str, country: str) -> dict[str, str]:
    return {
        "url": image_url,
        "country": country,
        "photographer_name": "",
        "photographer_url": "",
        "unsplash_url": "",
        "source": "local",
    }


def _search_unsplash(destination: str, access_key: str) -> dict[str, str] | None:
    endpoint = (
        "https://api.unsplash.com/search/photos"
        f"?query={quote_plus(destination + ' travel city')}&per_page=1&orientation=landscape"
    )
    request = Request(
        endpoint,
        headers={
            "Accept-Version": "v1",
            "Authorization": f"Client-ID {access_key}",
            "User-Agent": "TripMate-Portfolio/1.0",
        },
    )
    try:
        with urlopen(request, timeout=2.5) as response:
            payload: dict[str, Any] = json.load(response)
        result = payload["results"][0]
        image_url = result["urls"]["regular"]
        raw_photographer_name = result["user"]["name"]
        photographer_name = (
            raw_photographer_name.strip()
            if isinstance(raw_photographer_name, str)
            else ""
        )
        photographer_url = _safe_photographer_url(result["user"]["links"]["html"])
        if (
            _is_safe_image_url(image_url)
            and photographer_name
            and photographer_url
        ):
            return {
                "url": image_url,
                "photographer_name": photographer_name,
                "photographer_url": photographer_url,
                "unsplash_url": _UNSPLASH_HOME_URL,
                "source": "unsplash",
            }
    except (OSError, TimeoutError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    return None


def _is_safe_image_url(image_url: object) -> bool:
    if not isinstance(image_url, str):
        return False
    try:
        parsed = urlparse(image_url)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "images.unsplash.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


def _safe_photographer_url(profile_url: object) -> str | None:
    if not isinstance(profile_url, str):
        return None
    try:
        parsed = urlparse(profile_url)
        if not (
            parsed.scheme == "https"
            and parsed.hostname == "unsplash.com"
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and parsed.path.startswith("/@")
        ):
            return None
    except ValueError:
        return None

    query = urlencode({"utm_source": "tripmate", "utm_medium": "referral"})
    return urlunparse(("https", "unsplash.com", parsed.path, "", query, ""))
