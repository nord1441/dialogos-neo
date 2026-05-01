from __future__ import annotations

import html

import markdown

from .attachments import IMAGE_REF_RE


_MD = markdown.Markdown(
    extensions=[
        "fenced_code",
        "tables",
        "codehilite",
        "sane_lists",
    ],
    extension_configs={
        "codehilite": {"guess_lang": False, "css_class": "codehilite"},
    },
    output_format="html",
)


def render_markdown(text: str) -> str:
    _MD.reset()
    return _MD.convert(text)


def render_plain(text: str) -> str:
    return f"<pre>{html.escape(text)}</pre>"


def render_user_html(text: str, profile_slug: str) -> str:
    """Render a user message: escape everything, then re-inject inline
    images referenced via `![alt](attachments/...)` so screenshots show up."""
    out_parts: list[str] = []
    last = 0
    for m in IMAGE_REF_RE.finditer(text):
        out_parts.append(html.escape(text[last:m.start()]))
        alt = html.escape(m.group("alt"), quote=True)
        rel = m.group("path")
        name = rel.split("/", 1)[1]
        slug = html.escape(profile_slug, quote=True)
        url = f"/p/{slug}/attachments/{html.escape(name, quote=True)}"
        out_parts.append(
            f'<img class="attached" src="{url}" alt="{alt}" loading="lazy" />'
        )
        last = m.end()
    out_parts.append(html.escape(text[last:]))
    return f'<div class="user-text">{"".join(out_parts)}</div>'
