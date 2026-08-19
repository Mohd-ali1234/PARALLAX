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


# --- recovering tool calls that a model wrote as plain text -----------------
#
# qwen2.5-coder and similar models advertise tool support but put the call in
# `content` instead of `tool_calls`. Recovery must be eager enough to help and
# narrow enough never to mangle a real answer.

KNOWN = {"count_documents", "list_documents"}


def parse_content(content: str, known: set[str] | None = KNOWN) -> Any:
    body = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    return LLMClient._parse(body, known)


def test_recovers_a_bare_json_tool_call() -> None:
    msg = parse_content('{"name": "count_documents", "arguments": {"source_type": "xbrl"}}')

    assert msg.wants_tools
    assert msg.tool_calls[0].function.name == "count_documents"
    assert json.loads(msg.tool_calls[0].function.arguments) == {"source_type": "xbrl"}
    # Content is cleared, or the model would see its own call echoed back as prose.
    assert msg.content is None


def test_recovers_a_fenced_json_tool_call() -> None:
    msg = parse_content('```json\n{"name": "list_documents", "arguments": {}}\n```')
    assert msg.tool_calls[0].function.name == "list_documents"


def test_recovers_the_nested_function_form() -> None:
    msg = parse_content('{"function": {"name": "count_documents", "arguments": {}}}')
    assert msg.tool_calls[0].function.name == "count_documents"


def test_recovers_several_calls_from_a_list() -> None:
    msg = parse_content('[{"name": "count_documents"}, {"name": "list_documents"}]')
    assert [c.function.name for c in msg.tool_calls] == ["count_documents", "list_documents"]
    assert len({c.id for c in msg.tool_calls}) == 2  # ids must be distinct


def test_missing_arguments_become_an_empty_object() -> None:
    msg = parse_content('{"name": "count_documents"}')
    assert msg.tool_calls[0].function.arguments == "{}"


def test_ignores_a_name_that_is_not_a_real_tool() -> None:
    # The safety property: never invent a call for something we did not offer.
    msg = parse_content('{"name": "delete_everything", "arguments": {}}')
    assert not msg.wants_tools
    assert msg.content is not None


def test_ignores_prose() -> None:
    msg = parse_content("There are 4 documents in the registry.")
    assert not msg.wants_tools


def test_ignores_json_that_is_a_genuine_answer() -> None:
    msg = parse_content('{"total": 4, "by_type": {"xbrl": 1}}')
    assert not msg.wants_tools
    assert msg.content is not None


def test_no_recovery_when_no_tools_were_offered() -> None:
    msg = parse_content('{"name": "count_documents", "arguments": {}}', known=set())
    assert not msg.wants_tools


def test_structured_tool_calls_are_left_alone() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '{"name": "list_documents"}',
                    "tool_calls": [
                        {
                            "id": "real_1",
                            "type": "function",
                            "function": {"name": "count_documents", "arguments": "{}"},
                        }
                    ],
                }
            }
        ]
    }
    msg = LLMClient._parse(body, KNOWN)

    # A model that fills tool_calls properly must never be second-guessed.
    assert len(msg.tool_calls) == 1
    assert msg.tool_calls[0].id == "real_1"
