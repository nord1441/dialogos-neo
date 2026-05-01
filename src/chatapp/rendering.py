from __future__ import annotations

import html

import markdown


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
