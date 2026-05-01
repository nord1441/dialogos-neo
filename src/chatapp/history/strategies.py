from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from ..profiles.models import ProfileConfig


DAILY_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
SESSION_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}-\d{4})\.md$")


def now(profile: ProfileConfig) -> datetime:
    if profile.behavior.timezone == "utc":
        return datetime.now(timezone.utc)
    return datetime.now()


def history_dir(profile: ProfileConfig) -> Path:
    return profile.root / "history"


def current_history_path(profile: ProfileConfig) -> Path:
    """The file new messages will be appended to."""
    strategy = profile.behavior.history_strategy
    if strategy == "single":
        return profile.root / "history.md"
    if strategy == "daily":
        d = now(profile).strftime("%Y-%m-%d")
        return history_dir(profile) / f"{d}.md"
    if strategy == "session":
        # Reuse most recent session file unless the gap is too large or it's missing.
        latest = latest_session_file(profile)
        if latest is not None:
            gap_h = (now(profile) - _session_dt(latest.name)).total_seconds() / 3600.0
            if gap_h <= profile.behavior.session_gap_hours:
                return latest
        return new_session_path(profile)
    raise ValueError(f"unknown strategy: {strategy}")


def list_history_files(profile: ProfileConfig) -> list[Path]:
    strategy = profile.behavior.history_strategy
    if strategy == "single":
        p = profile.root / "history.md"
        return [p] if p.exists() else []

    hd = history_dir(profile)
    if not hd.exists():
        return []
    pattern = DAILY_NAME_RE if strategy == "daily" else SESSION_NAME_RE
    files = [p for p in hd.iterdir() if p.is_file() and pattern.match(p.name)]
    files.sort(key=lambda p: p.name)
    return files


def latest_session_file(profile: ProfileConfig) -> Path | None:
    files = [
        p for p in list_history_files(profile)
        if SESSION_NAME_RE.match(p.name)
    ]
    return files[-1] if files else None


def new_session_path(profile: ProfileConfig) -> Path:
    stamp = now(profile).strftime("%Y-%m-%d-%H%M")
    return history_dir(profile) / f"{stamp}.md"


def _session_dt(name: str) -> datetime:
    m = SESSION_NAME_RE.match(name)
    if not m:
        raise ValueError(name)
    return datetime.strptime(m.group(1), "%Y-%m-%d-%H%M")


def find_history_by_name(profile: ProfileConfig, name: str) -> Path | None:
    """Resolve a user-provided history name like '2026-05-01' or
    '2026-05-01-1430'. Returns None if not found or invalid."""
    if "/" in name or ".." in name or "\\" in name:
        return None
    candidate_names = [f"{name}.md", name]
    hd = history_dir(profile)
    for cn in candidate_names:
        p = hd / cn
        if p.exists() and p.is_file():
            return p
    return None
