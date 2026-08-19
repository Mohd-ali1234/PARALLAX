"""Agent-loop tests.

The LLM is stubbed with scripted turns, so these run anywhere - no model server,
no network. What is under test is the loop and the registry, not the model.
"""

from __future__ import annotations

import pytest

from parallax.ai.agent import Agent
from parallax.ai.llm import AssistantMessage, LLMClient, LLMError
from parallax.ai.tools import ToolContext, ToolRegistry

from fakes import FakeLLM, tool_turn


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()

    @reg.tool(
        name="echo",
        description="Echo a message back.",
        parameters={
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    )
    async def echo(ctx: ToolContext, message: str) -> str:
        return f"echo: {message}"

    return reg


@pytest.fixture
def ctx() -> ToolContext:
    # None of these tests reach the database.
    return ToolContext(session=None)  # type: ignore[arg-type]


async def test_answers_directly_when_no_tool_needed(registry, ctx) -> None:
    llm = FakeLLM([AssistantMessage(content="Hello.")])
    result = await Agent(llm, registry).run("hi", ctx)

    assert result.answer == "Hello."
    assert result.steps == []
    assert result.iterations == 1
    assert result.stop_reason == "final_answer"


async def test_executes_tool_then_answers(registry, ctx) -> None:
    llm = FakeLLM(
        [
            tool_turn("echo", '{"message": "ping"}'),
            AssistantMessage(content="It said ping."),
        ]
    )
    result = await Agent(llm, registry).run("echo ping", ctx)

    assert result.answer == "It said ping."
    assert [s.tool for s in result.steps] == ["echo"]
    assert result.steps[0].result == "echo: ping"
    assert result.iterations == 2


async def test_tool_result_is_fed_back_to_the_model(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"message": "x"}'), AssistantMessage(content="done")])
    await Agent(llm, registry).run("q", ctx)

    # Second request must carry the assistant tool_calls turn and the tool result.
    second = llm.calls[1]
    assert second[-1]["role"] == "tool"
    assert second[-1]["content"] == "echo: x"
    assert second[-1]["tool_call_id"] == "call_1"
    assert second[-2]["role"] == "assistant"


async def test_unknown_tool_is_reported_to_the_model_not_raised(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("nope"), AssistantMessage(content="recovered")])
    result = await Agent(llm, registry).run("q", ctx)

    assert result.answer == "recovered"
    assert "no tool named 'nope'" in result.steps[0].result
    assert "echo" in result.steps[0].result  # lists what is available


async def test_malformed_arguments_are_reported_not_raised(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", "{not json"), AssistantMessage(content="recovered")])
    result = await Agent(llm, registry).run("q", ctx)

    assert "not valid JSON" in result.steps[0].result
    assert result.answer == "recovered"


async def test_wrong_arguments_are_reported_not_raised(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"wrong": 1}'), AssistantMessage(content="recovered")])
    result = await Agent(llm, registry).run("q", ctx)

    assert "bad arguments" in result.steps[0].result
    assert result.answer == "recovered"


async def test_stops_at_max_iterations(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"message": "loop"}') for _ in range(10)])
    result = await Agent(llm, registry, max_iterations=3).run("q", ctx)

    assert result.stop_reason == "max_iterations"
    assert result.iterations == 3
    assert len(result.steps) == 3
    assert "Stopped after 3" in result.answer


async def test_registry_rejects_duplicate_names(registry) -> None:
    with pytest.raises(ValueError, match="already registered"):

        @registry.tool(name="echo", description="dupe")
        async def _dupe(ctx: ToolContext) -> str:
            return ""


def test_schemas_are_openai_shaped(registry) -> None:
    schema = registry.schemas()[0]
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "echo"
    assert schema["function"]["parameters"]["required"] == ["message"]


def test_parse_rejects_empty_choices() -> None:
    with pytest.raises(LLMError, match="no choices"):
        LLMClient._parse({"choices": []})


def test_parse_tolerates_null_tool_calls() -> None:
    # Several local servers send tool_calls: null instead of omitting the field.
    body = {"choices": [{"message": {"role": "assistant", "content": "hi", "tool_calls": None}}]}
    msg = LLMClient._parse(body)
    assert msg.tool_calls == []
    assert msg.wants_tools is False
