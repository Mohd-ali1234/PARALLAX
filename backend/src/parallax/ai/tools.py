"""A tiny tool registry.

Schemas are declared explicitly rather than derived from signatures. It is more
typing, but what the model sees is exactly what is written here - and for tool
calling, the description *is* the interface.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from parallax.core.exceptions import NotFoundError
from parallax.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class ToolContext:
    """Everything a tool is allowed to reach. Explicit, so tools stay testable."""

    session: AsyncSession


ToolFn = Callable[..., Awaitable[str]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: ToolFn

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def tool(
        self, name: str, description: str, parameters: dict[str, Any] | None = None
    ) -> Callable[[ToolFn], ToolFn]:
        def decorator(fn: ToolFn) -> ToolFn:
            if name in self.tools:
                raise ValueError(f"Tool {name!r} is already registered")
            self.tools[name] = Tool(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}},
                fn=fn,
            )
            return fn

        return decorator

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self.tools.values()]

    async def call(self, name: str, raw_arguments: str, ctx: ToolContext) -> str:
        """Run a tool. Never raises for model-caused problems.

        A bad tool name or malformed arguments is the model's mistake, and it can
        recover if we hand the error back as an observation. Letting it propagate
        would abort a run the model could have fixed itself.
        """
        tool = self.tools.get(name)
        if tool is None:
            known = ", ".join(sorted(self.tools)) or "none"
            return f"Error: no tool named {name!r}. Available tools: {known}."

        try:
            arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
        except json.JSONDecodeError as exc:
            return f"Error: arguments were not valid JSON ({exc})."

        if not isinstance(arguments, dict):
            return "Error: arguments must be a JSON object."

        log.info("tool_call", tool=name, arguments=arguments)
        try:
            return await tool.fn(ctx, **arguments)
        except NotFoundError as exc:
            return f"Error: {exc.message}"
        except TypeError as exc:
            # Wrong or missing parameters - the model can correct this.
            return f"Error: bad arguments for {name!r} ({exc})."
