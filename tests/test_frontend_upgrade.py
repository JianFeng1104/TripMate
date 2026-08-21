import io
import json

import pytest

from tripmate.image_resolver import (
    clear_destination_image_cache,
    get_destination_image,
    get_destination_visual,
)

from .conftest import create_trip


GENERIC_FALLBACK = "/static/img/travel-fallback.jpg"


def _unsplash_payload(
    *,
    image_url="https://images.unsplash.com/photo-london?ixid=test",
    photographer_url="https://unsplash.com/@ada-photo",
):
    return json.dumps(
        {
            "results": [
                {
                    "urls": {"regular": image_url},
                    "user": {
                        "name": "Ada Photo",
                        "links": {"html": photographer_url},
                    },
                }
            ]
        }
    ).encode()


def test_landing_exposes_final_product_value_proposition(client):
    page = client.get("/").get_data(as_text=True)

    assert "Find Your Next" in page
    assert "Travel Matching" in page
    assert "Compatibility Score" in page
    assert "Read-only Travel Assistant" in page


def test_tokyo_without_provider_key_uses_matching_bundled_image(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    clear_destination_image_cache()

    visual = get_destination_visual("Japan · Tokyo")

    assert visual["url"] == "/static/img/tokyo-night.jpg"
    assert visual["country"] == "Japan"
    assert visual["source"] == "local"
    assert not visual["photographer_name"]


def test_dali_without_provider_key_uses_matching_bundled_image(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    clear_destination_image_cache()

    visual = get_destination_visual("中国 · 大理")

    assert visual["url"] == "/static/img/dali-lake.jpg"
    assert visual["country"] == "China"
    assert visual["source"] == "local"


def test_london_without_provider_key_uses_only_generic_fallback(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    clear_destination_image_cache()

    visual = get_destination_visual("London")

    assert visual["url"] == GENERIC_FALLBACK
    assert visual["country"] == "United Kingdom"
    assert visual["source"] == "local"
    assert visual["url"] not in {
        "/static/img/tokyo-night.jpg",
        "/static/img/penang-waterfront.jpg",
        "/static/img/dali-lake.jpg",
    }


def test_unsplash_result_includes_safe_attribution_and_is_cached(monkeypatch):
    calls = []
    payload = _unsplash_payload()

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(payload)

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")
    monkeypatch.setattr("tripmate.image_resolver.urlopen", fake_urlopen)
    clear_destination_image_cache()

    first = get_destination_visual("London")
    second = get_destination_visual("London")

    assert first == second
    assert get_destination_image("London") == first["url"]
    assert first["url"] == "https://images.unsplash.com/photo-london?ixid=test"
    assert first["country"] == "United Kingdom"
    assert first["photographer_name"] == "Ada Photo"
    assert first["photographer_url"] == (
        "https://unsplash.com/@ada-photo?utm_source=tripmate&utm_medium=referral"
    )
    assert first["unsplash_url"] == (
        "https://unsplash.com/?utm_source=tripmate&utm_medium=referral"
    )
    assert first["source"] == "unsplash"
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("image_url", "photographer_url"),
    [
        ("https://example.com/fake-london.jpg", "https://unsplash.com/@ada-photo"),
        (
            "https://images.unsplash.com@evil.example/fake-london.jpg",
            "https://unsplash.com/@ada-photo",
        ),
        (
            "https://images.unsplash.com/photo-london",
            "https://evil.example/@ada-photo",
        ),
    ],
)
def test_malicious_or_untrusted_unsplash_urls_use_generic_fallback(
    monkeypatch, image_url, photographer_url
):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")
    monkeypatch.setattr(
        "tripmate.image_resolver.urlopen",
        lambda _request, timeout: io.BytesIO(
            _unsplash_payload(
                image_url=image_url,
                photographer_url=photographer_url,
            )
        ),
    )
    clear_destination_image_cache()

    visual = get_destination_visual("London")

    assert visual["url"] == GENERIC_FALLBACK
    assert visual["source"] == "local"
    assert not visual["photographer_url"]


def test_unsplash_timeout_uses_generic_fallback(monkeypatch):
    def timeout_urlopen(_request, timeout):
        raise TimeoutError

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")
    monkeypatch.setattr("tripmate.image_resolver.urlopen", timeout_urlopen)
    clear_destination_image_cache()

    visual = get_destination_visual("London")

    assert visual["url"] == GENERIC_FALLBACK
    assert visual["source"] == "local"


def test_unsplash_attribution_is_rendered_on_list_and_detail(app, auth, client):
    visual = {
        "url": "https://images.unsplash.com/photo-london?ixid=test",
        "country": "United Kingdom",
        "photographer_name": "Ada Photo",
        "photographer_url": (
            "https://unsplash.com/@ada-photo?utm_source=tripmate&utm_medium=referral"
        ),
        "unsplash_url": "https://unsplash.com/?utm_source=tripmate&utm_medium=referral",
        "source": "unsplash",
    }
    app.jinja_env.globals["destination_visual"] = lambda _destination: dict(visual)
    auth.register()
    create_trip(client, destination="London")

    list_page = client.get("/trips").get_data(as_text=True)
    detail_page = client.get("/trips/1").get_data(as_text=True)

    for page in (list_page, detail_page):
        assert "Photo by" in page
        assert "Ada Photo" in page
        assert visual["photographer_url"].replace("&", "&amp;") in page
        assert visual["unsplash_url"].replace("&", "&amp;") in page


def test_product_shell_includes_accessible_mobile_navigation(client):
    page = client.get("/").get_data(as_text=True)

    assert 'data-nav-toggle' in page
    assert 'aria-controls="primary-nav"' in page
    assert 'id="main-content"' in page
