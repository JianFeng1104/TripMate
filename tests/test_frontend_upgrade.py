import io

from tripmate.image_resolver import (
    clear_destination_image_cache,
    get_destination_image,
    get_destination_visual,
)


def test_landing_exposes_final_product_value_proposition(client):
    page = client.get("/").get_data(as_text=True)

    assert "Find Your Next" in page
    assert "Travel Matching" in page
    assert "Compatibility Score" in page
    assert "Read-only Travel Assistant" in page


def test_destination_visual_uses_local_fallback_without_provider_key(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    clear_destination_image_cache()

    visual = get_destination_visual("Japan · Tokyo")

    assert visual == {"url": "/static/img/tokyo-night.jpg", "country": "Japan"}


def test_destination_image_provider_result_is_cached(monkeypatch):
    calls = []
    payload = b'{"results":[{"urls":{"regular":"https://images.unsplash.com/photo-test"}}]}'

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(payload)

    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "test-key")
    monkeypatch.setattr("tripmate.image_resolver.urlopen", fake_urlopen)
    clear_destination_image_cache()

    assert get_destination_image("London") == "https://images.unsplash.com/photo-test"
    assert get_destination_image("London") == "https://images.unsplash.com/photo-test"
    assert len(calls) == 1


def test_product_shell_includes_accessible_mobile_navigation(client):
    page = client.get("/").get_data(as_text=True)

    assert 'data-nav-toggle' in page
    assert 'aria-controls="primary-nav"' in page
    assert 'id="main-content"' in page
