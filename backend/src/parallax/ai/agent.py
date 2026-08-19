"""A small tool-calling agent: prompt, call tools, repeat until it answers.

Hand-rolled rather than LangGraph on purpose. The whole loop is ~40 lines and
has no dependency; when the supervisor/critic graph from the architecture lands,
LangGraph earns its place. It does not yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from parallax.ai.llm import AssistantMessage, LLMClient
from parallax.ai.tools import ToolContext, ToolRegistry
from parallax.core.config import settings
from parallax.core.logging import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """You are the PARALLAX assistant. PARALLAX is a financial \
verification engine that ingests SEC filings, investor decks, earnings-call \
audio and XBRL facts, then cross-checks the numbers between them.

Answer questions about the ingested document registry using the tools provided.

Rules:
- Call a tool whenever the answer depends on data. Never guess at counts, \
titles or statuses.
- If a tool reports an error, read it and correct your call.
- Base your answer only on tool results. If the tools cannot answer, say so \
plainly.
- Be concise."""


@dataclass
class AgentStep:
    """One tool invocation, kept so callers can show their work."""

    tool: str
    arguments: str
    result: str


@dataclass
class AgentResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    iterations: int = 0
    stop_reason: Literal["final_answer", "max_iterations"] = "final_answer"
    model: str = ""


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry,
        *,
        system_prompt: str = SYSTEM_PROMPT,
        max_iterations: int | None = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations or settings.agent_max_iterations

    async def run(self, question: str, ctx: ToolContext) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]
        schemas = self.registry.schemas()
        steps: list[AgentStep] = []
        last: AssistantMessage | None = None

        for iteration in range(1, self.max_iterations + 1):
            last = await self.llm.chat(messages, tools=schemas)

            if not last.wants_tools:
                return AgentResult(
                    answer=(last.content or "").strip(),
                    steps=steps,
                    iterations=iteration,
                    stop_reason="final_answer",
                    model=self.llm.model,
                )

            messages.append(last.to_wire())
            for call in last.tool_calls:
                result = await self.registry.call(call.function.name, call.function.arguments, ctx)
                steps.append(
                    AgentStep(
                        tool=call.function.name,
                        arguments=call.function.arguments,
                        result=result,
                    )
                )
                messages.append({"role": "tool", "tool_call_id": call.id, "content": result})

        # Out of iterations while still asking for tools. Return what we have
        # rather than raising - the steps are often informative on their own.
        log.warning("agent_max_iterations", iterations=self.max_iterations, steps=len(steps))
        return AgentResult(
            answer=(last.content if last and last.content else "").strip()
            or f"Stopped after {self.max_iterations} tool-calling rounds without a final answer.",
            steps=steps,
            iterations=self.max_iterations,
            stop_reason="max_iterations",
            model=self.llm.model,
        )
