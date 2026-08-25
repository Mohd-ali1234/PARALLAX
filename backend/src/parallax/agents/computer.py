"""The computer support specialist."""

from __future__ import annotations

from parallax.agents.base import ToolAgent
from parallax.core.config import settings
from parallax.llm.client import LLMClient
from parallax.tools import computer as computer_tools

NAME = "computer"

DESCRIPTION = (
    "Handles laptops and desktops: hardware faults, boot problems, crashes, "
    "drivers, operating systems, performance, and warranty or repair cover."
)

SYSTEM_PROMPT = """You are the computer support specialist for a hardware company.

You handle laptops and desktops: hardware faults, drivers, operating systems
and warranty cover.

Rules:
- Call a tool whenever the answer depends on the customer's specific machine.
  Never invent a warranty date, serial number, driver version or test result.
- If a tool reports an error, read it and correct your call.
- If you need the serial number and it was not given, say so instead of
  guessing one.
- Answer in two or three sentences, plainly, as if speaking to the customer."""


def build(llm: LLMClient | None = None) -> ToolAgent:
    return ToolAgent(
        name=NAME,
        description=DESCRIPTION,
        system_prompt=SYSTEM_PROMPT,
        registry=computer_tools.registry,
        llm=llm or LLMClient(model=settings.model_for("computer")),
    )
