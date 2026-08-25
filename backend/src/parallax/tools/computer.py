"""Computer support tools.

Canned responses, same as the mobile set - see tools/mobile.py for why.
"""

from __future__ import annotations

from parallax.tools.base import ToolContext, ToolRegistry

registry = ToolRegistry()


@registry.tool(
    name="check_warranty",
    description=(
        "Look up warranty cover for a laptop or desktop by serial number: "
        "model, expiry date and what the cover includes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "serial_number": {
                "type": "string",
                "description": "The serial number printed on the device, e.g. 5CD1234ABC.",
            }
        },
        "required": ["serial_number"],
    },
)
async def check_warranty(ctx: ToolContext, serial_number: str) -> str:
    return (
        f"Serial {serial_number}: Dell XPS 15 9520, purchased 14 March 2025. "
        "Warranty ACTIVE until 14 March 2027 (Premium Support). "
        "Covers parts, labour and on-site repair. Accidental damage NOT covered."
    )


@registry.tool(
    name="lookup_driver_updates",
    description=(
        "Check which drivers are out of date for a given operating system. "
        "Use for crashes, display glitches, or missing audio."
    ),
    parameters={
        "type": "object",
        "properties": {
            "operating_system": {
                "type": "string",
                "description": "The customer's OS, e.g. Windows 11 or Ubuntu 24.04.",
            }
        },
        "required": ["operating_system"],
    },
)
async def lookup_driver_updates(ctx: ToolContext, operating_system: str) -> str:
    return (
        f"Driver check for {operating_system}: 3 updates available. "
        "Intel Iris Xe graphics 31.0.101.5460 (recommended, fixes display flicker), "
        "Realtek audio 6.0.9569.1 (optional), "
        "chipset 10.1.19444.8378 (recommended). Reboot required after install."
    )


@registry.tool(
    name="run_hardware_diagnostic",
    description=(
        "Run a remote diagnostic on one hardware component and report whether "
        "it passed. Valid components: battery, disk, memory, fan, display."
    ),
    parameters={
        "type": "object",
        "properties": {
            "component": {
                "type": "string",
                "enum": ["battery", "disk", "memory", "fan", "display"],
                "description": "Which component to test.",
            }
        },
        "required": ["component"],
    },
)
async def run_hardware_diagnostic(ctx: ToolContext, component: str) -> str:
    results = {
        "battery": "PASS. Health 87% of design capacity, 412 cycles. Normal for age.",
        "disk": "PASS. SMART status OK, 0 reallocated sectors, 2% wear. Temp 41C.",
        "memory": "FAIL. 2 errors detected in slot B during extended test. "
        "Recommend reseating or replacing the module in slot B.",
        "fan": "PASS. Fan spins up to 4200 RPM, no obstruction. Temp under load 78C.",
        "display": "PASS. No dead pixels, backlight uniform, panel reports no errors.",
    }
    outcome = results.get(component)
    if outcome is None:
        valid = ", ".join(sorted(results))
        return f"Error: unknown component {component!r}. Valid components: {valid}."
    return f"Diagnostic on {component}: {outcome}"
