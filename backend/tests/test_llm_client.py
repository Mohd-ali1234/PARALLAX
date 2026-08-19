"""LLMClient tests driving the real request path via a mock transport.

These exercise everything except the socket: payload construction, tool_calls
parsing, and how transport-level failures map onto PARALLAX errors.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from parallax.ai.llm import LLMClient, LLMError
from parallax.core.exceptions import DependencyUnavailableError

TOOLS = [
    {
        "type": "function",
        "function": {"name": "count_documents", "description": "count", "parameters": {}},
    }
]


def client_returning(payload: dict[str, Any], status: int = 200) -> tuple[LLMClient, list[dict]]:
    """An LLMClient whose server always answers `payload`, plus a capture list."""
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(
            {
                "url": str(request.url),
                "auth": request.headers.get("Authorization"),
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(status, json=payload)

    llm = LLMClient(
        base_url="http://model.test/v1",
        model="test-model",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )
    return llm, captured


async def test_sends_openai_shaped_payload() -> None:
    llm, captured = client_returning(
        {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
    )
    await llm.chat([{"role": "user", "content": "q"}], tools=TOOLS)

    sent = captured[0]
    assert sent["url"] == "http://model.test/v1/chat/completions"
    assert sent["auth"] == "Bearer secret"
    assert sent["body"]["model"] == "test-model"
    assert sent["body"]["stream"] is False
    assert sent["body"]["tool_choice"] == "auto"
    assert sent["body"]["tools"] == TOOLS


async def test_omits_tool_choice_when_no_tools() -> None:
    llm, captured = client_returning(
        {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}
    )
    await llm.chat([{"role": "user", "content": "q"}])

    assert "tools" not in captured[0]["body"]
    assert "tool_choice" not in captured[0]["body"]


async def test_parses_a_real_tool_calls_response() -> None:
    """The wire shape a tool-calling model actually returns."""
    llm, _ = client_returning(
        {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc",
                                "type": "function",
                                "function": {
                                    "name": "count_documents",
                                    "arguments": '{"source_type": "xbrl"}',
                                },
                            }
                        ],
                    },
                }
            ]
        }
    )
    msg = await llm.chat([{"role": "user", "content": "how many?"}], tools=TOOLS)

    assert msg.wants_tools
    assert msg.tool_calls[0].id == "call_abc"
    assert msg.tool_calls[0].function.name == "count_documents"
    assert json.loads(msg.tool_calls[0].function.arguments) == {"source_type": "xbrl"}

    # And it must round-trip back into the next request's history.
    wire = msg.to_wire()
    assert wire["role"] == "assistant"
    assert wire["tool_calls"][0]["function"]["name"] == "count_documents"


async def test_http_error_becomes_llm_error() -> None:
    llm, _ = client_returning({"error": "model not found"}, status=404)
    with pytest.raises(LLMError, match="404"):
        await llm.chat([{"role": "user", "content": "q"}])


async def test_connection_failure_becomes_503() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    llm = LLMClient(
        base_url="http://model.test/v1",
        model="m",
        api_key="k",
        transport=httpx.MockTransport(refuse),
    )
    with pytest.raises(DependencyUnavailableError) as exc:
        await llm.chat([{"role": "user", "content": "q"}])

    assert exc.value.status_code == 503
    assert "not reachable" in exc.value.message
