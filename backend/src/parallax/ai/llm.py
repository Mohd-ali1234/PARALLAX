"""Minimal client for an OpenAI-compatible chat-completions endpoint.

Ollama, LM Studio, llama.cpp's server and vLLM all expose this shape, so which
local runtime you run is a config value rather than a code change. Nothing here
is specific to a vendor beyond the URL.
"""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from parallax.core.config import settings
from parallax.core.exceptions import DependencyUnavailableError, ParallaxError
from parallax.core.logging import get_logger

log = get_logger(__name__)


class LLMError(ParallaxError):
    """The model server answered, but not with something usable."""

    status_code = 502
    code = "llm_error"


class ToolCallFunction(BaseModel):
    name: str
    arguments: str = "{}"


class ToolCall(BaseModel):
    id: str = ""
    type: str = "function"
    function: ToolCallFunction


class AssistantMessage(BaseModel):
    """The assistant turn: either prose, or a request to run tools."""

    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)

    def to_wire(self) -> dict[str, Any]:
        """Re-serialize for the next request's message history."""
        msg: dict[str, Any] = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        return msg


class LLMClient:
    """One method, one job: send messages and tools, get a message back."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        # Local servers ignore the key, but most reject a missing Authorization
        # header outright, so always send something.
        self.api_key = api_key or settings.llm_api_key
        self.timeout_s = timeout_s or settings.llm_timeout_s
        # Only set in tests, to drive the real request path without a server.
        self.transport = transport

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AssistantMessage:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.llm_temperature if temperature is None else temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s, transport=self.transport
            ) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
        except httpx.RequestError as exc:
            log.error("llm_unreachable", base_url=self.base_url, error=str(exc))
            raise DependencyUnavailableError(
                f"Local LLM at {self.base_url} is not reachable. Is the model server running?",
                details={"base_url": self.base_url, "model": self.model},
            ) from exc

        if response.status_code >= 400:
            raise LLMError(
                f"Model server returned {response.status_code}",
                details={"body": response.text[:500], "model": self.model},
            )

        return self._parse(response.json())

    @staticmethod
    def _parse(body: dict[str, Any]) -> AssistantMessage:
        choices = body.get("choices")
        if not choices:
            raise LLMError("Model response contained no choices", details={"body": body})

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LLMError("Model response contained no message", details={"body": body})

        # Some servers emit tool_calls: null rather than omitting the key.
        if message.get("tool_calls") is None:
            message = {**message, "tool_calls": []}

        return AssistantMessage.model_validate(message)
