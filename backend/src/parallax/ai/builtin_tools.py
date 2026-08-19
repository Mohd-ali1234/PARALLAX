"""Tools the agent can actually call, over the real document registry.

Deliberately read-only. An agent that can mutate ingestion state is a much
larger conversation about authorization than this scaffold should settle.
"""

from __future__ import annotations

from sqlalchemy import func, select

from parallax.ai.tools import ToolContext, ToolRegistry
from parallax.db.models.document import Document, DocumentStatus, SourceType

registry = ToolRegistry()

_SOURCE_TYPES = [s.value for s in SourceType]


def _parse_source_type(value: str | None) -> tuple[SourceType | None, str | None]:
    """Parse a source_type argument coming from the model.

    Returns (filter, error): `filter` is None for "no filter", `error` is a
    message to hand back to the model, or None.

    A tuple rather than "the enum or an error string" on purpose - SourceType is
    a StrEnum, so isinstance(x, str) is true for valid values too and cannot
    tell a result from an error.
    """
    if not value:
        return None, None
    try:
        return SourceType(value), None
    except ValueError:
        return (
            None,
            f"Error: unknown source_type {value!r}. Valid values: {', '.join(_SOURCE_TYPES)}.",
        )


@registry.tool(
    name="count_documents",
    description=(
        "Count ingested source documents, optionally filtered by source type. "
        "Use this for 'how many' questions."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_type": {
                "type": "string",
                "enum": _SOURCE_TYPES,
                "description": "Restrict the count to one source type. Omit to count all.",
            }
        },
    },
)
async def count_documents(ctx: ToolContext, source_type: str | None = None) -> str:
    parsed, error = _parse_source_type(source_type)
    if error is not None:
        return error

    stmt = select(func.count()).select_from(Document)
    if parsed is not None:
        stmt = stmt.where(Document.source_type == parsed)

    total = await ctx.session.scalar(stmt) or 0
    scope = f" of type {parsed.value}" if parsed else ""
    return f"{total} document(s){scope}."


@registry.tool(
    name="list_documents",
    description=(
        "List ingested documents with their title, source type, fiscal period and "
        "processing status. Use this when the user asks what has been ingested."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_type": {
                "type": "string",
                "enum": _SOURCE_TYPES,
                "description": "Restrict to one source type. Omit for all.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum rows to return (1-20).",
                "minimum": 1,
                "maximum": 20,
            },
        },
    },
)
async def list_documents(ctx: ToolContext, source_type: str | None = None, limit: int = 10) -> str:
    parsed, error = _parse_source_type(source_type)
    if error is not None:
        return error

    limit = max(1, min(int(limit), 20))
    stmt = select(Document).order_by(Document.created_at.desc()).limit(limit)
    if parsed is not None:
        stmt = stmt.where(Document.source_type == parsed)

    rows = (await ctx.session.scalars(stmt)).all()
    if not rows:
        return "No documents match that filter."

    lines = []
    for d in rows:
        period = f"FY{d.fiscal_year}" if d.fiscal_year else "period unknown"
        if d.fiscal_year and d.fiscal_quarter:
            period = f"FY{d.fiscal_year} Q{d.fiscal_quarter}"
        lines.append(f"- {d.title} | {d.source_type.value} | {period} | status={d.status.value}")
    return "\n".join(lines)


@registry.tool(
    name="ingestion_status",
    description=(
        "Break down documents by processing status (pending, parsing, extracting, "
        "indexed, failed). Use this to answer whether ingestion is complete or stuck."
    ),
    parameters={"type": "object", "properties": {}},
)
async def ingestion_status(ctx: ToolContext) -> str:
    stmt = select(Document.status, func.count()).group_by(Document.status)
    rows = (await ctx.session.execute(stmt)).all()
    if not rows:
        return "No documents have been ingested yet."

    counts = {status.value: count for status, count in rows}
    parts = [f"{counts.get(s.value, 0)} {s.value}" for s in DocumentStatus if counts.get(s.value)]
    return "Document status breakdown: " + ", ".join(parts) + "."
