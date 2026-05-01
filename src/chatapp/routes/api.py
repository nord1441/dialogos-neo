from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth.bearer import require_bearer
from ..history import parser as history_parser
from ..history import strategies
from ..profiles.loader import list_profiles
from ..services import collect_response, get_profile_or_404, send_and_stream


router = APIRouter(prefix="/api", dependencies=[Depends(require_bearer)])


@router.get("/profiles")
async def api_profiles(request: Request):
    settings = request.app.state.settings
    profs = list_profiles(settings.profiles_root)
    return {
        "profiles": [
            {
                "slug": p.slug,
                "display_name": p.meta.display_name,
                "icon": p.meta.icon,
                "model": p.model.name,
                "provider": p.model.provider,
                "history_strategy": p.behavior.history_strategy,
            }
            for p in profs
        ]
    }


@router.get("/profiles/{profile}/history")
async def api_history(profile: str, request: Request, name: str | None = None):
    settings = request.app.state.settings
    prof = get_profile_or_404(settings, profile)

    if name:
        path = strategies.find_history_by_name(prof, name)
        if path is None:
            raise HTTPException(status_code=404, detail="history not found")
    else:
        path = strategies.current_history_path(prof)

    msgs = history_parser.parse_file(path)
    return {
        "history_file": path.relative_to(prof.root).as_posix() if path.exists() else None,
        "messages": [{"role": m.role, "content": m.content} for m in msgs],
    }


@router.post("/profiles/{profile}/messages")
async def api_post_message(profile: str, request: Request):
    settings = request.app.state.settings
    keys = request.app.state.keys
    prof = get_profile_or_404(settings, profile)

    payload = await request.json() if (await request.body()) else {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid JSON body")

    content = str(payload.get("content", "")).strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    wait = bool(payload.get("wait_for_response", True))

    stream = await send_and_stream(settings, keys, prof, content)

    if not wait:
        # Fire-and-forget: drain in the background and return immediately.
        # We still need to consume the iterator for the assistant message to
        # be saved, so we run it inline but don't return the text.
        async for _ in stream.chunks:
            pass
        return {
            "user_message_saved": True,
            "history_file": stream.history_path_rel,
        }

    text = await collect_response(stream)
    return {
        "user_message_saved": True,
        "assistant_response": text,
        "history_file": stream.history_path_rel,
    }
