from __future__ import annotations

from pathlib import Path

from ..profiles.models import Message


def format_message(msg: Message) -> str:
    body = msg.content.rstrip("\n")
    return f"## {msg.role}\n{body}\n"


def append_message(path: Path, msg: Message) -> None:
    """Append a message block to a history file. Creates the file (and parent
    dirs) if missing. Ensures a single blank line precedes the new block when
    the file is non-empty.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    block = format_message(msg)

    if path.exists() and path.stat().st_size > 0:
        existing = path.read_text(encoding="utf-8")
        sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
        with path.open("a", encoding="utf-8") as f:
            f.write(sep + block + "\n")
    else:
        path.write_text(block + "\n", encoding="utf-8")
