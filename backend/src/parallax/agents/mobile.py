"""The mobile support specialist."""

from __future__ import annotations

from parallax.agents.base import ToolAgent
from parallax.core.config import settings
from parallax.llm.client import LLMClient
from parallax.tools import mobile as mobile_tools

NAME = "mobile"

DESCRIPTION = (
    "Handles mobile phones and tariffs: device faults, signal and network "
    "problems, SIM cards, data allowances, roaming, billing on a mobile plan, "
    "and voicemail."
)

SYSTEM_PROMPT = """You are the mobile support specialist for a telecoms company.

You handle phones, SIM cards, mobile networks, tariffs and voicemail.

Rules:
- Call a tool whenever the answer depends on the customer's account or device.
  Never invent a plan name, data figure, PIN or device model.
- If a tool reports an error, read it and correct your call.
- If you need the customer's phone number and it was not given, say so instead
  of guessing one.
- Answer in two or three sentences, plainly, as if speaking to the customer."""


def build(llm: LLMClient | None = None) -> ToolAgent:
    return ToolAgent(
        name=NAME,
        description=DESCRIPTION,
        system_prompt=SYSTEM_PROMPT,
        registry=mobile_tools.registry,
        llm=llm or LLMClient(model=settings.model_for("mobile")),
    )
