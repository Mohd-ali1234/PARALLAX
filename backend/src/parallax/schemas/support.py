"""Request and response models for the support desk."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000, description="The customer's message.")


class RouteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent: Literal["mobile", "computer", "none"]
    reason: str
    fallback_used: bool


class StepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool: str
    arguments: str
    result: str


class DelegateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent: str
    #: The specialist's own wording, before the supervisor rewrote it.
    answer: str
    steps: list[StepRead]
    iterations: int
    stop_reason: Literal["final_answer", "max_iterations"]
    model: str


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    note: str
    changed: bool


class AskResponse(BaseModel):
    """The final reply, plus every stage that produced it.

    The trace is not decoration: when an answer is wrong you need to know
    whether routing, the tool call, or the review is at fault.
    """

    answer: str
    route: RouteRead
    delegate: DelegateRead | None
    review: ReviewRead
    stages: list[str]
    model: str
