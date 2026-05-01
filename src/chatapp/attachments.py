from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from .profiles.models import ProfileConfig


# Image extension -> media type. Matches what Anthropic and OpenAI accept.
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

# Hard cap to keep base64 payloads sane. Most providers cap at ~5-10 MiB;
# 8 MiB raw → ~10.7 MiB base64 is below typical limits.
MAX_BYTES = 8 * 1024 * 1024

# Match `![alt](path)` where path is a relative attachments/ ref.
# Avoid http(s):// and absolute paths.
IMAGE_REF_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<path>(?!https?://|/)attachments/[A-Za-z0-9._\-]+)\)"
)


@dataclass(frozen=True)
class AttachmentRef:
    rel_path: str  # e.g. "attachments/abc123.png"
    media_type: str
    alt: str = ""


def media_type_for(name: str) -> str | None:
    suffix = Path(name).suffix.lower()
    return ALLOWED_EXTENSIONS.get(suffix)


class AttachmentError(Exception):
    pass


def save_upload(
    profile: ProfileConfig,
    filename: str,
    data: bytes,
) -> AttachmentRef:
    media_type = media_type_for(filename)
    if media_type is None:
        raise AttachmentError(
            f"unsupported file type: {Path(filename).suffix or '(no extension)'}"
        )
    if len(data) == 0:
        raise AttachmentError("empty file")
    if len(data) > MAX_BYTES:
        raise AttachmentError(
            f"file too large: {len(data)} bytes (max {MAX_BYTES})"
        )

    profile.attachments_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    name = f"{uuid.uuid4().hex}{suffix}"
    out = profile.attachments_dir / name
    out.write_bytes(data)
    return AttachmentRef(
        rel_path=f"attachments/{name}",
        media_type=media_type,
    )


def resolve(profile: ProfileConfig, rel_path: str) -> Path | None:
    """Resolve a `attachments/...` ref to an absolute path, scoped to the
    profile root. Returns None if the path escapes or the file is missing.
    """
    if not rel_path.startswith("attachments/"):
        return None
    if ".." in rel_path.split("/"):
        return None
    candidate = (profile.root / rel_path).resolve()
    try:
        candidate.relative_to(profile.attachments_dir.resolve())
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def extract_refs(text: str) -> list[AttachmentRef]:
    """Find every `![alt](attachments/...)` reference in a message body.
    Returns refs in order of appearance, deduplicated by rel_path."""
    seen: set[str] = set()
    out: list[AttachmentRef] = []
    for m in IMAGE_REF_RE.finditer(text):
        rel = m.group("path")
        if rel in seen:
            continue
        mt = media_type_for(rel)
        if mt is None:
            continue
        seen.add(rel)
        out.append(AttachmentRef(rel_path=rel, media_type=mt, alt=m.group("alt")))
    return out


def encode_base64(profile: ProfileConfig, ref: AttachmentRef) -> str | None:
    p = resolve(profile, ref.rel_path)
    if p is None:
        return None
    return base64.standard_b64encode(p.read_bytes()).decode("ascii")
