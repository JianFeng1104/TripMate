"""Safe presentation helpers for untrusted Agent output."""

from markupsafe import Markup
import bleach
import markdown


_ALLOWED_TAGS = frozenset(
    {
        "p",
        "strong",
        "em",
        "ul",
        "ol",
        "li",
        "h2",
        "h3",
        "h4",
        "code",
        "pre",
        "br",
        "blockquote",
    }
)


def render_agent_markdown(answer: str) -> Markup:
    """Render Agent Markdown and return only allowlist-sanitized HTML.

    Agent text is untrusted provider output. Markdown conversion happens before
    Bleach removes raw HTML, event handlers, links and other unsafe markup.
    ``Markup`` is applied only to the sanitized result consumed by Jinja.
    """

    rendered = markdown.markdown(
        answer,
        extensions=("fenced_code", "nl2br", "sane_lists"),
        output_format="html",
    )
    sanitized = bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes={},
        protocols=("http", "https"),
        strip=True,
    )
    return Markup(sanitized)
