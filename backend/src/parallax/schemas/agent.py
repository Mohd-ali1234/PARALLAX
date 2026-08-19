"""Agent request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class AgentStepRead(BaseModel):
    tool: str
    arguments: str
    result: str


class AskResponse(BaseModel):
    answer: str
    # The tool calls behind the answer. PARALLAX shows its work by design.
    steps: list[AgentStepRead]
    iterations: int
    stop_reason: Literal["final_answer", "max_iterations"]
    model: str
