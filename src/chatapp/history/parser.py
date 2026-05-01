from __future__ import annotations

import re
from pathlib import Path

from ..profiles.models import Message


ROLE_HEADER_RE = re.compile(r"^## (user|assistant|system)\s*$")


def parse(text: str) -> list[Message]:
    """Parse history Markdown into a list of Messages.

    Format:
        ## user
        ...body...

        ## assistant
        ...body...

    Only an exact-match line `## user|assistant|system` (no trailing words)
    is treated as a role boundary. Any other `##` lines stay in the body.
    """
    lines = text.splitlines()
    messages: list[Message] = []

    current_role: str | None = None
    current_buf: list[str] = []

    def flush() -> None:
        if current_role is None:
            return
        # Strip leading and trailing blank lines from the body.
        body = "\n".join(current_buf).strip("\n")
        # Remove trailing whitespace-only lines but keep internal structure.
        body = body.rstrip()
        messages.append(Message(role=current_role, content=body))

    for line in lines:
        m = ROLE_HEADER_RE.match(line)
        if m:
            flush()
            current_role = m.group(1)
            current_buf = []
        else:
            if current_role is not None:
                current_buf.append(line)

    flush()

    # Drop empty trailing messages with no content.
    while messages and messages[-1].content == "":
        messages.pop()

    return messages


def parse_file(path: Path) -> list[Message]:
    if not path.exists():
        return []
    return parse(path.read_text(encoding="utf-8"))
