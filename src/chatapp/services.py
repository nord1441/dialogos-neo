from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import HTTPException, status

from .config import Settings
from .history import parser as history_parser
from .history import strategies, writer
from .history.lock import LockTimeout, profile_lock
from .llm.base import CompletionRequest, LLMError
from .llm.factory import get_provider
from .profiles.loader import (
    InvalidProfile,
    ProfileNotFound,
    load_profile,
    read_system_prompt,
)
from .profiles.models import Message, ProfileConfig


@dataclass
class StreamResult:
    profile: ProfileConfig
    history_path_rel: str
    chunks: AsyncIterator[str]


def get_profile_or_404(settings: Settings, slug: str) -> ProfileConfig:
    try:
        return load_profile(settings.profiles_root, slug)
    except ProfileNotFound:
        raise HTTPException(status_code=404, detail=f"profile not found: {slug}")
    except InvalidProfile as e:
        raise HTTPException(status_code=500, detail=str(e))


def resolve_api_key(profile: ProfileConfig, keys: dict[str, str]) -> str:
    ref = profile.api.key_ref
    if not ref:
        # Local providers (llama.cpp etc.) often need no key.
        if profile.model.provider == "local":
            return ""
        raise HTTPException(
            status_code=500,
            detail=f"profile '{profile.slug}' has no api.key_ref",
        )
    key = keys.get(ref.lower())
    if not key:
        raise HTTPException(
            status_code=500,
            detail=f"key_ref '{ref}' not found in keystore",
        )
    return key


async def send_and_stream(
    settings: Settings,
    keys: dict[str, str],
    profile: ProfileConfig,
    user_content: str,
) -> StreamResult:
    """Append user message, kick off LLM stream. Caller must consume the
    stream; the assistant message is appended to history when streaming
    finishes successfully.
    """
    user_content = user_content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="empty content")

    api_key = resolve_api_key(profile, keys)
    provider = get_provider(profile.model.provider)
    history_path = strategies.current_history_path(profile)

    # Acquire lock and append user message synchronously, then release once we
    # have the full message list and start streaming. Re-acquire to append the
    # final assistant text.
    try:
        with profile_lock(profile.lock_path, timeout=2.0):
            history_path.parent.mkdir(parents=True, exist_ok=True)
            existing = history_parser.parse_file(history_path)
            user_msg = Message(role="user", content=user_content)
            writer.append_message(history_path, user_msg)
            messages = existing + [user_msg]
            system = read_system_prompt(profile)
    except LockTimeout:
        raise HTTPException(status_code=409, detail="profile is busy")

    req = CompletionRequest(
        profile=profile,
        api_key=api_key,
        system=system,
        messages=messages,
    )

    rel_path = history_path.relative_to(profile.root).as_posix()

    async def gen() -> AsyncIterator[str]:
        buffer: list[str] = []
        try:
            async for chunk in provider.stream(req):
                buffer.append(chunk)
                yield chunk
        except LLMError as e:
            # Surface a final chunk so the client sees the failure context.
            err = f"\n\n_[error: {e}]_"
            buffer.append(err)
            yield err
            # Save what we have so the conversation isn't lost.
        finally:
            full = "".join(buffer).strip()
            if full and profile.behavior.auto_save:
                try:
                    with profile_lock(profile.lock_path, timeout=5.0):
                        writer.append_message(
                            history_path,
                            Message(role="assistant", content=full),
                        )
                except LockTimeout:
                    # Can't get lock; drop a sidecar file instead.
                    sidecar = history_path.with_suffix(history_path.suffix + ".pending")
                    sidecar.write_text(
                        f"## assistant\n{full}\n",
                        encoding="utf-8",
                    )

    return StreamResult(profile=profile, history_path_rel=rel_path, chunks=gen())


async def collect_response(stream: StreamResult) -> str:
    parts: list[str] = []
    async for chunk in stream.chunks:
        parts.append(chunk)
    return "".join(parts).strip()
