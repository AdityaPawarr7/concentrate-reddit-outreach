"""Format Reddit post bodies for safe HTML display."""

from __future__ import annotations

import html
import re

import bleach
import markdown

ALLOWED_TAGS = frozenset(
    bleach.sanitizer.ALLOWED_TAGS
    | {
        "p",
        "br",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "code",
        "blockquote",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "a",
        "img",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "hr",
        "del",
        "sup",
        "div",
        "span",
    }
)

ALLOWED_ATTRS = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "title", "width", "height"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
    "div": ["class"],
    "span": ["class"],
}

_HTML_HINT = re.compile(r"<\s*(table|div|p|a|br|span|h[1-6]|ul|ol|pre|blockquote|img)\b", re.I)


def normalize_author(author: str) -> str:
    return re.sub(r"^\/?u\/", "", (author or "").strip()) or "[deleted]"


def format_post_html(raw: str) -> str:
    """Render markdown or RSS HTML as sanitized Reddit-style HTML."""
    if not raw or not raw.strip():
        return '<p class="empty-body">(No body)</p>'

    text = raw.strip()
    if _HTML_HINT.search(text):
        cleaned = bleach.clean(text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    else:
        rendered = markdown.markdown(
            text,
            extensions=["fenced_code", "tables", "nl2br", "sane_lists"],
        )
        cleaned = bleach.clean(rendered, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

    # Force external links to open safely
    cleaned = re.sub(
        r'<a\s+([^>]*href=)',
        r'<a rel="noopener noreferrer" target="_blank" \1',
        cleaned,
        flags=re.I,
    )
    return cleaned or f'<p>{html.escape(text)}</p>'
