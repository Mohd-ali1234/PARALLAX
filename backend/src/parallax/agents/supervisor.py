"""The supervisor: route the query, delegate it, review what comes back.

Three explicit stages rather than giving the supervisor the specialists as
tools. Both designs work; this one was chosen because every stage is separately
visible in the response, which is what makes the pipeline debuggable - you can
see whether a bad answer came from bad routing, a bad tool call, or a bad
review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from parallax.agents import computer as computer_agent
from parallax.agents import mobile as mobile_agent
from parallax.agents.base import AgentResult, ToolAgent
from parallax.core.config import settings
from parallax.core.logging import get_logger
from parallax.llm.client import LLMClient
from parallax.tools.base import ToolContext

log = get_logger(__name__)

RouteName = Literal["mobile", "computer", "none"]
ROUTE_NAMES: tuple[RouteName, ...] = ("mobile", "computer", "none")

# Used only when the model's routing reply cannot be read. Crude on purpose:
# it is a safety net, not the routing strategy.
_MOBILE_HINTS = frozenset(
    [
        "phone",
        "mobile",
        "smartphone",
        "sim",
        "signal",
        "roaming",
        "voicemail",
        "tariff",
        "airtime",
        "4g",
        "5g",
        "android",
        "iphone",
        "handset",
        "text",
        "sms",
        "call",
    ]
)
_COMPUTER_HINTS = frozenset(
    [
        "laptop",
        "desktop",
        "pc",
        "computer",
        "macbook",
        "boot",
        "bios",
        "driver",
        "drivers",
        "windows",
        "macos",
        "linux",
        "keyboard",
        "trackpad",
        "ssd",
        "hard",
        "disk",
        "ram",
        "memory",
        "warranty",
        "bluescreen",
        "crash",
        "overheating",
        "fan",
    ]
)


@dataclass
class RouteDecision:
    agent: RouteName
    reason: str
    #: True when the model's reply was unreadable and the keyword net decided.
    fallback_used: bool = False


@dataclass
class ReviewDecision:
    note: str
    #: True when the supervisor's final wording differs from the specialist draft.
    changed: bool = False


@dataclass
class SupervisorResult:
    answer: str
    route: RouteDecision
    review: ReviewDecision
    delegate: AgentResult | None = None
    model: str = ""
    stages: list[str] = field(default_factory=list)


ROUTING_PROMPT = """You are the routing supervisor on a customer support desk.

Read the customer's message and choose exactly one specialist:

mobile   - {mobile}
computer - {computer}
none     - the message is about neither, or is just chit-chat.

Reply with ONE word and nothing else: mobile, computer, or none."""

REVIEW_PROMPT = """You are the supervisor on a customer support desk. A \
specialist has drafted a reply to a customer. Write the final reply that will \
be sent.

Rules:
- Keep every fact from the draft exactly as it is. Do not add details the
  specialist did not give: no invented dates, numbers, PINs or model names.
- If the draft does not actually answer the question, say plainly what is
  still needed instead of pretending it does.
- Two or three sentences, warm and direct. Write to the customer, not about
  them. Do not mention the specialist, the tools or this review."""

NO_ROUTE_PROMPT = """You are the supervisor on a customer support desk that \
only covers mobile phones and computers.

The customer's message falls outside both. Reply in one or two sentences: be
polite, say what the desk can help with, and invite them to rephrase. Do not
attempt to answer the question itself."""


def _extract_route(reply: str) -> RouteName | None:
    """Read a routing reply, but only when it is unambiguous.

    A first-match scan would misread "this is not a computer issue, it is
    mobile". So: trust the first word if it is a label, otherwise accept the
    reply only when exactly one distinct label appears in it.
    """
    text = reply.strip().lower()
    if not text:
        return None

    first = re.split(r"[^a-z]+", text, maxsplit=1)[0]
    if first in ROUTE_NAMES:
        return first

    found = {name for name in ROUTE_NAMES if re.search(rf"\b{name}\b", text)}
    if len(found) == 1:
        return found.pop()
    return None


def _keyword_route(query: str) -> RouteName:
    words = set(re.findall(r"[a-z]+", query.lower()))
    mobile_score = len(words & _MOBILE_HINTS)
    computer_score = len(words & _COMPUTER_HINTS)

    if mobile_score == computer_score:
        return "none"
    return "mobile" if mobile_score > computer_score else "computer"


class Supervisor:
    def __init__(
        self,
        *,
        llm: LLMClient | None = None,
        mobile: ToolAgent | None = None,
        computer: ToolAgent | None = None,
    ) -> None:
        self.llm = llm or LLMClient(model=settings.model_for("supervisor"))
        self.mobile = mobile or mobile_agent.build()
        self.computer = computer or computer_agent.build()

    @property
    def specialists(self) -> dict[str, ToolAgent]:
        return {self.mobile.name: self.mobile, self.computer.name: self.computer}

    async def handle(self, query: str, ctx: ToolContext) -> SupervisorResult:
        stages: list[str] = []

        route = await self._route(query)
        stages.append(f"route -> {route.agent}")
        log.info(
            "supervisor_route",
            agent=route.agent,
            fallback=route.fallback_used,
        )

        if route.agent == "none":
            answer = await self._answer_out_of_scope(query)
            stages.append("no delegation")
            return SupervisorResult(
                answer=answer,
                route=route,
                review=ReviewDecision(note="Out of scope; answered by the supervisor."),
                delegate=None,
                model=self.llm.model,
                stages=stages,
            )

        specialist = self.specialists[route.agent]
        delegate = await specialist.run(query, ctx)
        stages.append(f"{specialist.name} -> {len(delegate.steps)} tool call(s)")

        final, review = await self._review(query, delegate)
        stages.append("review -> final answer")

        return SupervisorResult(
            answer=final,
            route=route,
            review=review,
            delegate=delegate,
            model=self.llm.model,
            stages=stages,
        )

    async def _route(self, query: str) -> RouteDecision:
        prompt = ROUTING_PROMPT.format(
            mobile=self.mobile.description, computer=self.computer.description
        )
        reply = await self.llm.chat(
            [{"role": "system", "content": prompt}, {"role": "user", "content": query}]
        )
        raw = (reply.content or "").strip()

        chosen = _extract_route(raw)
        if chosen is not None:
            return RouteDecision(agent=chosen, reason=raw[:200] or chosen)

        guess = _keyword_route(query)
        log.warning("supervisor_route_unreadable", reply=raw[:200], fallback=guess)
        return RouteDecision(
            agent=guess,
            reason=f"Routing reply was unclear ({raw[:80]!r}); fell back to keywords.",
            fallback_used=True,
        )

    async def _review(self, query: str, delegate: AgentResult) -> tuple[str, ReviewDecision]:
        handoff = (
            f"Customer's message:\n{query}\n\n"
            f"Specialist ({delegate.agent}) draft reply:\n{delegate.answer}"
        )
        if delegate.steps:
            looked_up = "\n".join(f"- {s.tool}: {s.result}" for s in delegate.steps)
            handoff += f"\n\nWhat the specialist looked up:\n{looked_up}"

        reply = await self.llm.chat(
            [
                {"role": "system", "content": REVIEW_PROMPT},
                {"role": "user", "content": handoff},
            ]
        )
        final = (reply.content or "").strip()

        if not final:
            # A model that returns nothing must not blank the customer's answer.
            return delegate.answer, ReviewDecision(
                note="Review returned nothing; sent the specialist draft unchanged.",
                changed=False,
            )

        changed = final.strip() != delegate.answer.strip()
        return final, ReviewDecision(
            note="Reviewed and rewritten." if changed else "Reviewed; draft sent as written.",
            changed=changed,
        )

    async def _answer_out_of_scope(self, query: str) -> str:
        reply = await self.llm.chat(
            [
                {"role": "system", "content": NO_ROUTE_PROMPT},
                {"role": "user", "content": query},
            ]
        )
        return (reply.content or "").strip() or (
            "Sorry - this desk only covers mobile phones and computers. "
            "Could you rephrase your question around one of those?"
        )
