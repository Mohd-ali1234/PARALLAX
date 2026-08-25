"""The specialist agent: prompt a model, run the tools it asks for, repeat.

Hand-rolled rather than a framework. The whole loop is about 40 lines and adds
no dependency, which keeps the pipeline easy to follow end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from parallax.core.config import settings
from parallax.core.logging import get_logger
from parallax.llm.client import AssistantMessage, LLMClient
from parallax.tools.base import ToolContext, ToolRegistry

log = get_logger(__name__)

StopReason = Literal["final_answer", "max_iterations"]


@dataclass
class AgentStep:
    """One tool invocation, kept so the supervisor and the caller can see the
    work rather than trusting the final sentence."""

    tool: str
    arguments: str
    result: str


@dataclass
class AgentResult:
    agent: str
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    iterations: int = 0
    stop_reason: StopReason = "final_answer"
    model: str = ""


class ToolAgent:
    """A named specialist: one system prompt, one toolset, one model.

    Mobile and computer support are the same class with different prompts and
    registries. That is deliberate - a "different agent" is a different brief
    and different capabilities, not different plumbing.
    """

    def __init__(
        self,
        *,
        name: str,
        description: str,
        system_prompt: str,
        registry: ToolRegistry,
        llm: LLMClient,
        max_iterations: int | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.registry = registry
        self.llm = llm
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
                    agent=self.name,
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

        # Out of rounds while still asking for tools. Return what we have - the
        # steps are usually informative even without a closing sentence.
        log.warning("agent_max_iterations", agent=self.name, iterations=self.max_iterations)
        return AgentResult(
            agent=self.name,
            answer=(last.content if last and last.content else "").strip()
            or f"Stopped after {self.max_iterations} tool-calling rounds without a final answer.",
            steps=steps,
            iterations=self.max_iterations,
            stop_reason="max_iterations",
            model=self.llm.model,
        )
