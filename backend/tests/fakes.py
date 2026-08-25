"""Test doubles shared across the agent tests."""

from __future__ import annotations

from typing import Any

from parallax.llm.client import AssistantMessage, LLMClient, ToolCall, ToolCallFunction


class FakeLLM(LLMClient):
    """Replays a fixed list of assistant turns and records what it was sent.

    Subclasses LLMClient rather than duck-typing it, so the agents' type
    contract is genuinely exercised.
    """

    def __init__(self, turns: list[AssistantMessage], *, model: str = "fake-model") -> None:
        self.turns = list(turns)
        self.calls: list[list[dict[str, Any]]] = []
        self.model = model
        self.base_url = "http://fake"
        self.api_key = "x"
        self.timeout_s = 1.0
        self.transport = None

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
    ) -> AssistantMessage:
        self.calls.append(list(messages))
        if not self.turns:
            raise AssertionError("FakeLLM ran out of scripted turns")
        return self.turns.pop(0)


def text_turn(content: str) -> AssistantMessage:
    """An ordinary prose reply."""
    return AssistantMessage(content=content)


def tool_turn(name: str, arguments: str = "{}", call_id: str = "call_1") -> AssistantMessage:
    """An assistant turn that asks for one tool call."""
    return AssistantMessage(
        content=None,
        tool_calls=[
            ToolCall(id=call_id, function=ToolCallFunction(name=name, arguments=arguments))
        ],
    )
