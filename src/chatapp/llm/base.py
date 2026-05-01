from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol

from ..profiles.models import Message, ProfileConfig


@dataclass
class CompletionRequest:
    profile: ProfileConfig
    api_key: str
    system: str
    messages: list[Message]


class LLMProvider(Protocol):
    async def stream(self, req: CompletionRequest) -> AsyncIterator[str]:
        """Yield text chunks of the assistant response."""
        ...


class LLMError(Exception):
    pass
