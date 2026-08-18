from pathlib import Path

from tripmate.presentation import render_agent_markdown


def test_agent_markdown_renders_strong_text():
    assert "<strong>Tokyo</strong>" in str(render_agent_markdown("**Tokyo**"))


def test_agent_markdown_renders_heading():
    assert "<h2>Tokyo</h2>" in str(render_agent_markdown("## Tokyo"))


def test_agent_markdown_renders_list():
    rendered = str(render_agent_markdown("- Tokyo\n- Osaka"))
    assert "<ul>" in rendered
    assert "<li>Tokyo</li>" in rendered
    assert "<li>Osaka</li>" in rendered


def test_agent_markdown_strips_script_html():
    rendered = str(render_agent_markdown("<script>alert(1)</script>"))
    assert "<script" not in rendered


def test_agent_markdown_strips_image_event_handler():
    rendered = str(render_agent_markdown("<img src=x onerror=alert(1)>"))
    assert "<img" not in rendered
    assert "onerror" not in rendered


def test_agent_markdown_does_not_create_javascript_link():
    rendered = str(render_agent_markdown("[javascript](javascript:alert(1))"))
    assert "javascript:" not in rendered
    assert "<a" not in rendered


def test_agent_markdown_keeps_plain_chinese_text():
    rendered = str(render_agent_markdown("这是普通的东京旅行说明。"))
    assert "这是普通的东京旅行说明。" in rendered
    assert rendered.startswith("<p>")


def test_travel_assistant_page_exposes_accessible_thinking_ui(client, auth):
    auth.register()
    page = client.get("/travel-assistant").get_data(as_text=True)

    assert "data-assistant-form" in page
    assert "data-assistant-loading" in page
    assert 'aria-live="polite"' in page
    assert "Thinking" in page


def test_travel_assistant_javascript_disables_submit_button():
    script = (
        Path(__file__).parents[1] / "tripmate" / "static" / "js" / "app.js"
    ).read_text(encoding="utf-8")

    assert 'addEventListener("submit"' in script
    assert "button.disabled = true" in script
    assert 'setAttribute("aria-busy", "true")' in script
