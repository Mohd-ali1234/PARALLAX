"""The specialist agent loop, and the static tools it calls."""

from __future__ import annotations

import pytest

from parallax.agents import computer as computer_agent
from parallax.agents import mobile as mobile_agent
from parallax.agents.base import ToolAgent
from parallax.tools.base import ToolContext, ToolRegistry

from fakes import FakeLLM, text_turn, tool_turn


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


def build(llm: FakeLLM, registry: ToolRegistry, **kwargs: object) -> ToolAgent:
    return ToolAgent(
        name="test",
        description="test agent",
        system_prompt="be helpful",
        registry=registry,
        llm=llm,
        **kwargs,  # type: ignore[arg-type]
    )


async def test_answers_directly_when_no_tool_needed(registry, ctx) -> None:
    agent = build(FakeLLM([text_turn("Hello.")]), registry)
    result = await agent.run("hi", ctx)

    assert result.answer == "Hello."
    assert result.steps == []
    assert result.stop_reason == "final_answer"
    assert result.agent == "test"


async def test_executes_tool_then_answers(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"message": "ping"}'), text_turn("It said ping.")])
    result = await build(llm, registry).run("echo ping", ctx)

    assert result.answer == "It said ping."
    assert [s.tool for s in result.steps] == ["echo"]
    assert result.steps[0].result == "echo: ping"
    assert result.iterations == 2


async def test_tool_result_is_fed_back_to_the_model(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"message": "x"}'), text_turn("done")])
    await build(llm, registry).run("q", ctx)

    second = llm.calls[1]
    assert second[-1]["role"] == "tool"
    assert second[-1]["content"] == "echo: x"
    assert second[-1]["tool_call_id"] == "call_1"
    assert second[-2]["role"] == "assistant"


async def test_unknown_tool_is_reported_not_raised(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("nope"), text_turn("recovered")])
    result = await build(llm, registry).run("q", ctx)

    assert result.answer == "recovered"
    assert "no tool named 'nope'" in result.steps[0].result
    assert "echo" in result.steps[0].result


async def test_malformed_arguments_are_reported_not_raised(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", "{not json"), text_turn("recovered")])
    result = await build(llm, registry).run("q", ctx)

    assert "not valid JSON" in result.steps[0].result
    assert result.answer == "recovered"


async def test_wrong_arguments_are_reported_not_raised(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"wrong": 1}'), text_turn("recovered")])
    result = await build(llm, registry).run("q", ctx)

    assert "bad arguments" in result.steps[0].result
    assert result.answer == "recovered"


async def test_stops_at_max_iterations(registry, ctx) -> None:
    llm = FakeLLM([tool_turn("echo", '{"message": "loop"}') for _ in range(10)])
    result = await build(llm, registry, max_iterations=3).run("q", ctx)

    assert result.stop_reason == "max_iterations"
    assert result.iterations == 3
    assert len(result.steps) == 3


async def test_registry_rejects_duplicate_names(registry) -> None:
    with pytest.raises(ValueError, match="already registered"):

        @registry.tool(name="echo", description="dupe")
        async def _dupe(ctx: ToolContext) -> str:
            return ""


# --- the real specialists ---------------------------------------------------


def test_specialists_hold_separate_toolsets() -> None:
    mobile = mobile_agent.build(FakeLLM([]))
    computer = computer_agent.build(FakeLLM([]))

    assert mobile.registry.names() == [
        "check_device_status",
        "lookup_data_plan",
        "reset_voicemail_pin",
    ]
    assert computer.registry.names() == [
        "check_warranty",
        "lookup_driver_updates",
        "run_hardware_diagnostic",
    ]
    # An agent must not be able to reach the other one's capabilities.
    assert not set(mobile.registry.names()) & set(computer.registry.names())


async def test_mobile_tools_return_canned_data(ctx) -> None:
    reg = mobile_agent.build(FakeLLM([])).registry

    plan = await reg.call("lookup_data_plan", '{"phone_number": "+447700900123"}', ctx)
    assert "+447700900123" in plan
    assert "Unlimited 5G" in plan

    pin = await reg.call("reset_voicemail_pin", '{"phone_number": "+447700900123"}', ctx)
    assert "reset" in pin.lower()


async def test_computer_tools_return_canned_data(ctx) -> None:
    reg = computer_agent.build(FakeLLM([])).registry

    warranty = await reg.call("check_warranty", '{"serial_number": "5CD1234ABC"}', ctx)
    assert "5CD1234ABC" in warranty
    assert "ACTIVE" in warranty

    memory = await reg.call("run_hardware_diagnostic", '{"component": "memory"}', ctx)
    assert "FAIL" in memory  # the one deliberately-failing component


async def test_diagnostic_rejects_an_unknown_component(ctx) -> None:
    reg = computer_agent.build(FakeLLM([])).registry
    result = await reg.call("run_hardware_diagnostic", '{"component": "flux capacitor"}', ctx)

    assert "unknown component" in result
    assert "battery" in result  # tells the model what it should have said
