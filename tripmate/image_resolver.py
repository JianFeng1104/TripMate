"""Presentation-only destination imagery with safe local fallbacks.

The resolver never reads or writes Trip records. When an Unsplash access key is
available it performs one bounded search request and caches the resulting image
URL in process memory. Local assets keep every card usable when the provider is
unconfigured or unavailable.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen


_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_CACHE_LOCK = threading.Lock()

_LOCAL_IMAGES = (
    "/static/img/tokyo-night.jpg",
    "/static/img/penang-waterfront.jpg",
    "/static/img/dali-lake.jpg",
)

_DESTINATION_HINTS = {
    "tokyo": ("Japan", _LOCAL_IMAGES[0]),
    "东京": ("Japan", _LOCAL_IMAGES[0]),
    "japan": ("Japan", _LOCAL_IMAGES[0]),
    "日本": ("Japan", _LOCAL_IMAGES[0]),
    "penang": ("Malaysia", _LOCAL_IMAGES[1]),
    "槟城": ("Malaysia", _LOCAL_IMAGES[1]),
    "malaysia": ("Malaysia", _LOCAL_IMAGES[1]),
    "马来西亚": ("Malaysia", _LOCAL_IMAGES[1]),
    "dali": ("China", _LOCAL_IMAGES[2]),
    "大理": ("China", _LOCAL_IMAGES[2]),
    "china": ("China", _LOCAL_IMAGES[2]),
    "中国": ("China", _LOCAL_IMAGES[2]),
    "london": ("United Kingdom", _LOCAL_IMAGES[1]),
    "伦敦": ("United Kingdom", _LOCAL_IMAGES[1]),
    "paris": ("France", _LOCAL_IMAGES[2]),
    "巴黎": ("France", _LOCAL_IMAGES[2]),
    "seoul": ("South Korea", _LOCAL_IMAGES[0]),
    "首尔": ("South Korea", _LOCAL_IMAGES[0]),
    "singapore": ("Singapore", _LOCAL_IMAGES[1]),
    "新加坡": ("Singapore", _LOCAL_IMAGES[1]),
}

_BUNDLED_DESTINATION_KEYS = {
    "tokyo", "东京", "japan", "日本",
    "penang", "槟城", "malaysia", "马来西亚",
    "dali", "大理", "china", "中国",
}


def get_destination_visual(destination: str) -> dict[str, str]:
    """Return a stable ``url`` and display ``country`` for a destination.

    The return value contains only presentation data and is safe to pass to a
    Jinja template. Provider failures are deliberately swallowed so a network
    outage cannot break Trip discovery.
    """

    normalized = " ".join((destination or "").strip().lower().split())
    fallback = _fallback_visual(normalized)
    if not normalized:
        return fallback

    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(normalized)
        if cached and cached[0] > now:
            return dict(cached[1])

    resolved = dict(fallback)
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    has_bundled_match = any(keyword in normalized for keyword in _BUNDLED_DESTINATION_KEYS)
    if access_key and not has_bundled_match:
        image_url = _search_unsplash(normalized, access_key)
        if image_url:
            resolved["url"] = image_url

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


def _fallback_visual(normalized: str) -> dict[str, str]:
    for keyword, (country, image_url) in _DESTINATION_HINTS.items():
        if keyword in normalized:
            return {"url": image_url, "country": country}

    digest = hashlib.sha256(normalized.encode("utf-8")).digest() if normalized else b"\0"
    return {"url": _LOCAL_IMAGES[digest[0] % len(_LOCAL_IMAGES)], "country": "Global"}


def _search_unsplash(destination: str, access_key: str) -> str | None:
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
        image_url = payload["results"][0]["urls"]["regular"]
        parsed = urlparse(image_url)
        if parsed.scheme == "https" and parsed.hostname == "images.unsplash.com":
            return image_url
    except (OSError, TimeoutError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    return None
