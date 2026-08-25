"""The supervisor: routing, delegation and review."""

from __future__ import annotations

import pytest

from parallax.agents import computer as computer_agent
from parallax.agents import mobile as mobile_agent
from parallax.agents.supervisor import Supervisor, _extract_route, _keyword_route

from fakes import FakeLLM, text_turn, tool_turn


def make_supervisor(
    supervisor_turns: list, mobile_turns: list | None = None, computer_turns: list | None = None
) -> Supervisor:
    return Supervisor(
        llm=FakeLLM(supervisor_turns, model="supervisor-model"),
        mobile=mobile_agent.build(FakeLLM(mobile_turns or [], model="mobile-model")),
        computer=computer_agent.build(FakeLLM(computer_turns or [], model="computer-model")),
    )


# --- routing ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("mobile", "mobile"),
        ("computer", "computer"),
        ("none", "none"),
        ("  Mobile.  ", "mobile"),
        ("COMPUTER", "computer"),
        ("computer - the customer mentions a laptop", "computer"),
    ],
)
def test_reads_a_clear_routing_reply(reply: str, expected: str) -> None:
    assert _extract_route(reply) == expected


@pytest.mark.parametrize(
    "reply",
    [
        "",
        "I am not sure what to do here.",
        # Names two labels without leading with one: genuinely ambiguous, and a
        # first-match scan would read this backwards.
        "This is not a computer issue, it is mobile.",
    ],
)
def test_rejects_an_unreadable_routing_reply(reply: str) -> None:
    assert _extract_route(reply) is None


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("my phone has no signal and the sim is dead", "mobile"),
        ("my laptop will not boot, the fan is loud", "computer"),
        ("what is the meaning of life", "none"),
    ],
)
def test_keyword_fallback(query: str, expected: str) -> None:
    assert _keyword_route(query) == expected


async def test_falls_back_to_keywords_when_the_model_is_unclear(ctx) -> None:
    supervisor = make_supervisor(
        supervisor_turns=[text_turn("hmm, hard to say"), text_turn("Final reply.")],
        mobile_turns=[text_turn("Mobile draft.")],
    )
    result = await supervisor.handle("my phone has no signal", ctx)

    assert result.route.agent == "mobile"
    assert result.route.fallback_used is True
    assert result.answer == "Final reply."


# --- the whole pipeline -----------------------------------------------------


async def test_routes_to_mobile_and_reviews_the_draft(ctx) -> None:
    supervisor = make_supervisor(
        supervisor_turns=[text_turn("mobile"), text_turn("Your plan is Unlimited 5G.")],
        mobile_turns=[
            tool_turn("lookup_data_plan", '{"phone_number": "+447700900123"}'),
            text_turn("The plan is Unlimited 5G."),
        ],
    )
    result = await supervisor.handle("what plan am I on? +447700900123", ctx)

    assert result.route.agent == "mobile"
    assert result.route.fallback_used is False
    assert result.delegate is not None
    assert result.delegate.agent == "mobile"
    assert [s.tool for s in result.delegate.steps] == ["lookup_data_plan"]
    assert result.answer == "Your plan is Unlimited 5G."
    assert result.review.changed is True
    assert result.stages == [
        "route -> mobile",
        "mobile -> 1 tool call(s)",
        "review -> final answer",
    ]


async def test_routes_to_computer(ctx) -> None:
    supervisor = make_supervisor(
        supervisor_turns=[text_turn("computer"), text_turn("Your warranty runs to 2027.")],
        computer_turns=[
            tool_turn("check_warranty", '{"serial_number": "5CD1234ABC"}'),
            text_turn("Warranty active until 14 March 2027."),
        ],
    )
    result = await supervisor.handle("is my laptop still under warranty? 5CD1234ABC", ctx)

    assert result.route.agent == "computer"
    assert result.delegate is not None
    assert result.delegate.agent == "computer"
    assert "5CD1234ABC" in result.delegate.steps[0].result


async def test_only_the_routed_specialist_is_called(ctx) -> None:
    mobile_llm = FakeLLM([text_turn("Mobile draft.")], model="mobile-model")
    computer_llm = FakeLLM([text_turn("Computer draft.")], model="computer-model")
    supervisor = Supervisor(
        llm=FakeLLM([text_turn("mobile"), text_turn("Final.")]),
        mobile=mobile_agent.build(mobile_llm),
        computer=computer_agent.build(computer_llm),
    )

    await supervisor.handle("my sim is not working", ctx)

    assert len(mobile_llm.calls) == 1
    assert computer_llm.calls == []  # the other specialist must stay untouched


async def test_out_of_scope_skips_delegation(ctx) -> None:
    supervisor = make_supervisor(
        supervisor_turns=[text_turn("none"), text_turn("We only cover phones and computers.")]
    )
    result = await supervisor.handle("book me a flight to Tokyo", ctx)

    assert result.route.agent == "none"
    assert result.delegate is None
    assert result.answer == "We only cover phones and computers."
    assert result.stages == ["route -> none", "no delegation"]


async def test_review_sees_the_draft_and_the_tool_results(ctx) -> None:
    supervisor_llm = FakeLLM([text_turn("mobile"), text_turn("Final.")])
    supervisor = Supervisor(
        llm=supervisor_llm,
        mobile=mobile_agent.build(
            FakeLLM(
                [
                    tool_turn("lookup_data_plan", '{"phone_number": "+447700900123"}'),
                    text_turn("Unlimited 5G."),
                ]
            )
        ),
        computer=computer_agent.build(FakeLLM([])),
    )
    await supervisor.handle("what is my plan? +447700900123", ctx)

    handoff = supervisor_llm.calls[1][-1]["content"]
    assert "Unlimited 5G." in handoff  # the draft
    assert "lookup_data_plan" in handoff  # and what produced it


async def test_empty_review_falls_back_to_the_draft(ctx) -> None:
    """A model that returns nothing must not blank the customer's answer."""
    supervisor = make_supervisor(
        supervisor_turns=[text_turn("mobile"), text_turn("   ")],
        mobile_turns=[text_turn("The specialist draft.")],
    )
    result = await supervisor.handle("my phone is broken", ctx)

    assert result.answer == "The specialist draft."
    assert result.review.changed is False
    assert "unchanged" in result.review.note


async def test_unchanged_review_is_reported_as_unchanged(ctx) -> None:
    supervisor = make_supervisor(
        supervisor_turns=[text_turn("mobile"), text_turn("Same wording.")],
        mobile_turns=[text_turn("Same wording.")],
    )
    result = await supervisor.handle("my phone is broken", ctx)

    assert result.review.changed is False
    assert result.answer == "Same wording."
