from __future__ import annotations

from .anthropic import AnthropicProvider
from .base import LLMProvider
from .openai import OpenAICompatibleProvider


def get_provider(name: str) -> LLMProvider:
    n = name.lower()
    if n == "anthropic":
        return AnthropicProvider()
    if n in ("openai", "openai_compatible", "local"):
        return OpenAICompatibleProvider()
    raise ValueError(f"unknown provider: {name}")
