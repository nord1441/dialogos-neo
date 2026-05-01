from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from ..attachments import encode_base64, extract_refs
from .base import CompletionRequest, LLMError


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _content_blocks(req: CompletionRequest, body: str) -> list[dict] | str:
    """Return either a plain string (no images) or a list of content blocks
    (text + image_b64)."""
    refs = extract_refs(body)
    if not refs:
        return body

    blocks: list[dict] = [{"type": "text", "text": body}] if body.strip() else []
    for ref in refs:
        data = encode_base64(req.profile, ref)
        if data is None:
            continue
        blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": ref.media_type,
                "data": data,
            },
        })
    if not blocks:
        return body
    return blocks


def _to_anthropic_messages(req: CompletionRequest) -> list[dict]:
    out: list[dict] = []
    for m in req.messages:
        if m.role == "system":
            out.append({"role": "user", "content": f"[system note]\n{m.content}"})
            continue
        if m.role not in ("user", "assistant"):
            continue
        if m.role == "user":
            out.append({"role": m.role, "content": _content_blocks(req, m.content)})
        else:
            out.append({"role": m.role, "content": m.content})
    return out


class AnthropicProvider:
    async def stream(self, req: CompletionRequest) -> AsyncIterator[str]:
        headers = {
            "x-api-key": req.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
            "accept": "text/event-stream",
        }
        body = {
            "model": req.profile.model.name,
            "max_tokens": req.profile.model.max_tokens,
            "temperature": req.profile.model.temperature,
            "top_p": req.profile.model.top_p,
            "stream": True,
            "messages": _to_anthropic_messages(req),
        }
        if req.system:
            body["system"] = req.system

        url = req.profile.model.endpoint or ANTHROPIC_URL

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code >= 400:
                    err_body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"anthropic {resp.status_code}: {err_body}")

                async for raw in resp.aiter_lines():
                    if not raw or not raw.startswith("data:"):
                        continue
                    data = raw[len("data:"):].strip()
                    if data == "[DONE]":
                        return
                    try:
                        evt = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    t = evt.get("type")
                    if t == "content_block_delta":
                        delta = evt.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text") or ""
                            if text:
                                yield text
                    elif t == "message_stop":
                        return
