"""Agent endpoint.

One question in, one answer out, with the tool calls that produced it. The
model runs wherever PARALLAX_LLM_BASE_URL points - by default a local server.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from parallax.ai.agent import Agent
from parallax.ai.builtin_tools import registry
from parallax.ai.llm import LLMClient
from parallax.ai.tools import ToolContext
from parallax.api.deps import SessionDep
from parallax.core.config import settings
from parallax.schemas.agent import AgentStepRead, AskRequest, AskResponse

router = APIRouter()


def get_agent() -> Agent:
    """Injected as a dependency so tests can override it and never need a
    running model server."""
    return Agent(LLMClient(), registry)


AgentDep = Annotated[Agent, Depends(get_agent)]


@router.post("/ask", response_model=AskResponse, status_code=status.HTTP_200_OK)
async def ask(payload: AskRequest, session: SessionDep, agent: AgentDep) -> AskResponse:
    """Ask the agent about the ingested document registry.

    Returns 503 if the configured LLM server is unreachable.
    """
    result = await agent.run(payload.question, ToolContext(session=session))

    return AskResponse(
        answer=result.answer,
        steps=[
            AgentStepRead(tool=s.tool, arguments=s.arguments, result=s.result) for s in result.steps
        ],
        iterations=result.iterations,
        stop_reason=result.stop_reason,
        model=result.model,
    )


@router.get("/tools", summary="List the tools the agent can call")
async def list_tools() -> dict[str, object]:
    return {
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "max_iterations": settings.agent_max_iterations,
        "tools": [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in registry.tools.values()
        ],
    }
