"""Customer support endpoint.

One message in, one reply out, with the routing decision, the specialist's tool
calls and the review that shaped it.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from parallax.agents.supervisor import Supervisor
from parallax.core.config import settings
from parallax.schemas.support import (
    AskRequest,
    AskResponse,
    DelegateRead,
    ReviewRead,
    RouteRead,
)
from parallax.tools.base import ToolContext

router = APIRouter()


def get_supervisor() -> Supervisor:
    """Injected as a dependency so tests can override it and never need a
    running model server."""
    return Supervisor()


SupervisorDep = Annotated[Supervisor, Depends(get_supervisor)]


@router.post("/ask", response_model=AskResponse, status_code=status.HTTP_200_OK)
async def ask(payload: AskRequest, supervisor: SupervisorDep) -> AskResponse:
    """Send a customer message through the supervisor.

    Returns 503 if the configured LLM server is unreachable.
    """
    ctx = ToolContext(request_id=str(uuid.uuid4()))
    result = await supervisor.handle(payload.message, ctx)

    return AskResponse(
        answer=result.answer,
        route=RouteRead.model_validate(result.route),
        delegate=(DelegateRead.model_validate(result.delegate) if result.delegate else None),
        review=ReviewRead.model_validate(result.review),
        stages=result.stages,
        model=result.model,
    )


@router.get("/agents", summary="List the agents and the tools they hold")
async def list_agents(supervisor: SupervisorDep) -> dict[str, object]:
    return {
        "supervisor": {
            "model": supervisor.llm.model,
            "stages": ["route", "delegate", "review"],
        },
        "base_url": settings.llm_base_url,
        "specialists": [
            {
                "name": agent.name,
                "description": agent.description,
                "model": agent.llm.model,
                "max_iterations": agent.max_iterations,
                "tools": [
                    {"name": t.name, "description": t.description, "parameters": t.parameters}
                    for t in agent.registry.tools.values()
                ],
            }
            for agent in supervisor.specialists.values()
        ],
    }
