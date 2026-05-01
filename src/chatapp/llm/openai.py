from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from ..attachments import encode_base64, extract_refs
from .base import CompletionRequest, LLMError


OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def _content_blocks(req: CompletionRequest, body: str) -> list[dict] | str:
    refs = extract_refs(body)
    if not refs:
        return body
    blocks: list[dict] = [{"type": "text", "text": body}] if body.strip() else []
    for ref in refs:
        data = encode_base64(req.profile, ref)
        if data is None:
            continue
        blocks.append({
            "type": "image_url",
            "image_url": {"url": f"data:{ref.media_type};base64,{data}"},
        })
    if not blocks:
        return body
    return blocks


class OpenAICompatibleProvider:
    """Works with OpenAI and any OpenAI-compatible endpoint
    (e.g. llama.cpp server, vLLM, LM Studio).
    """

    def __init__(self, default_url: str = OPENAI_URL):
        self._default_url = default_url

    async def stream(self, req: CompletionRequest) -> AsyncIterator[str]:
        url = req.profile.model.endpoint or self._default_url
        headers = {"content-type": "application/json"}
        if req.api_key:
            headers["authorization"] = f"Bearer {req.api_key}"

        msgs: list[dict] = []
        if req.system:
            msgs.append({"role": "system", "content": req.system})
        for m in req.messages:
            if m.role not in ("user", "assistant", "system"):
                continue
            content: list[dict] | str
            if m.role == "user":
                content = _content_blocks(req, m.content)
            else:
                content = m.content
            msgs.append({"role": m.role, "content": content})

        body = {
            "model": req.profile.model.name,
            "messages": msgs,
            "stream": True,
            "temperature": req.profile.model.temperature,
            "top_p": req.profile.model.top_p,
            "max_tokens": req.profile.model.max_tokens,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                if resp.status_code >= 400:
                    err_body = (await resp.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"openai-compat {resp.status_code}: {err_body}")

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
                    for choice in evt.get("choices", []):
                        delta = choice.get("delta") or {}
                        text = delta.get("content")
                        if text:
                            yield text
