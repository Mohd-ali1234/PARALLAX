"""Mobile support tools.

Every response is canned. The point of this build is to prove the pipeline -
supervisor routes, specialist calls a tool, supervisor reviews - so the tools
return fixed, realistic-looking strings instead of touching real systems.

To make one real, replace the body. Nothing else in the pipeline changes.
"""

from __future__ import annotations

from parallax.tools.base import ToolContext, ToolRegistry

registry = ToolRegistry()


@registry.tool(
    name="check_device_status",
    description=(
        "Look up the current status of a customer's mobile device: model, "
        "network connection, OS version and when it was last seen online."
    ),
    parameters={
        "type": "object",
        "properties": {
            "phone_number": {
                "type": "string",
                "description": "The customer's mobile number, e.g. +447700900123.",
            }
        },
        "required": ["phone_number"],
    },
)
async def check_device_status(ctx: ToolContext, phone_number: str) -> str:
    return (
        f"Device for {phone_number}: Samsung Galaxy S23 (SM-S911B). "
        "Network: connected, 5G, signal strength good. OS: Android 14, up to date. "
        "Last seen online: 12 minutes ago."
    )


@registry.tool(
    name="lookup_data_plan",
    description=(
        "Look up a customer's mobile tariff: plan name, data allowance, data "
        "used so far and when the billing cycle ends."
    ),
    parameters={
        "type": "object",
        "properties": {
            "phone_number": {
                "type": "string",
                "description": "The customer's mobile number.",
            }
        },
        "required": ["phone_number"],
    },
)
async def lookup_data_plan(ctx: ToolContext, phone_number: str) -> str:
    return (
        f"Plan for {phone_number}: Unlimited 5G, 24-month contract. "
        "Data used this cycle: 42.3 GB (no cap). Roaming: included in EU. "
        "Billing cycle ends on the 3rd of next month."
    )


@registry.tool(
    name="reset_voicemail_pin",
    description=(
        "Reset the voicemail PIN for a mobile number and send a temporary PIN "
        "by SMS. Use when the customer is locked out of voicemail."
    ),
    parameters={
        "type": "object",
        "properties": {
            "phone_number": {
                "type": "string",
                "description": "The customer's mobile number.",
            }
        },
        "required": ["phone_number"],
    },
)
async def reset_voicemail_pin(ctx: ToolContext, phone_number: str) -> str:
    return (
        f"Voicemail PIN for {phone_number} has been reset. "
        "A temporary PIN (4821) was sent by SMS and expires in 30 minutes. "
        "The customer should set a new PIN on first login."
    )
