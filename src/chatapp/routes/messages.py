from __future__ import annotations

import html
import json
import uuid

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..history import strategies
from ..rendering import render_markdown, render_user_html
from ..services import get_profile_or_404, send_and_stream


router = APIRouter()


@router.post("/p/{profile}/messages")
async def post_message_sse(profile: str, request: Request, content: str = Form(...)):
    settings = request.app.state.settings
    keys = request.app.state.keys
    prof = get_profile_or_404(settings, profile)

    stream = await send_and_stream(settings, keys, prof, content)
    msg_id = "m-" + uuid.uuid4().hex[:8]
    user_html = render_user_html(content.strip(), prof.slug)

    async def gen():
        # Frame the user message and an empty assistant container before the
        # stream so htmx can swap into the right targets.
        first = (
            f"event: setup\n"
            f"data: " + json.dumps({"id": msg_id, "user_html": user_html}) + "\n\n"
        )
        yield first

        buf: list[str] = []
        async for chunk in stream.chunks:
            buf.append(chunk)
            full = "".join(buf)
            rendered = (
                render_markdown(full)
                if prof.ui.markdown_render
                else "<pre>" + html.escape(full) + "</pre>"
            )
            payload = json.dumps({"id": msg_id, "html": rendered})
            yield f"event: chunk\ndata: {payload}\n\n"

        yield f"event: done\ndata: {json.dumps({'id': msg_id})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/p/{profile}/sessions")
async def new_session(profile: str, request: Request):
    settings = request.app.state.settings
    prof = get_profile_or_404(settings, profile)
    if prof.behavior.history_strategy != "session":
        raise HTTPException(
            status_code=400,
            detail="profile is not using session strategy",
        )
    new_path = strategies.new_session_path(prof)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if not new_path.exists():
        new_path.write_text("", encoding="utf-8")
    return {"history_file": new_path.relative_to(prof.root).as_posix()}
