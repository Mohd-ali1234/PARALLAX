"""Agent endpoint tests.

The /ask route gets a stubbed agent injected, so no model server is involved.
The tool tests do hit Postgres and skip without it.
"""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from parallax.ai.agent import Agent
from parallax.ai.builtin_tools import registry
from parallax.ai.llm import AssistantMessage
from parallax.ai.tools import ToolContext
from parallax.api.v1.routes.agent import get_agent
from parallax.db.models.document import Document, SourceType

from fakes import FakeLLM, tool_turn


async def test_tools_endpoint_lists_registered_tools(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/agent/tools")
    assert resp.status_code == 200

    body = resp.json()
    names = {t["name"] for t in body["tools"]}
    assert names == {"count_documents", "list_documents", "ingestion_status"}
    assert body["max_iterations"] >= 1


async def test_ask_returns_answer_and_steps(
    app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    llm = FakeLLM(
        [
            tool_turn("count_documents", "{}"),
            AssistantMessage(content="There are no documents yet."),
        ]
    )
    app.dependency_overrides[get_agent] = lambda: Agent(llm, registry)
    try:
        resp = await db_client.post("/api/v1/agent/ask", json={"question": "how many docs?"})
    finally:
        app.dependency_overrides.pop(get_agent, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "There are no documents yet."
    assert body["stop_reason"] == "final_answer"
    assert [s["tool"] for s in body["steps"]] == ["count_documents"]
    assert "0 document(s)" in body["steps"][0]["result"]


async def test_ask_rejects_empty_question(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/agent/ask", json={"question": ""})
    assert resp.status_code == 422


# --- the real tools, against a real database --------------------------------


async def _seed(session: AsyncSession) -> None:
    session.add_all(
        [
            Document(
                source_type=SourceType.SEC_FILING,
                title="ACME 10-K FY2025",
                storage_uri="s3://x/a.pdf",
                checksum="a" * 64,
                fiscal_year=2025,
            ),
            Document(
                source_type=SourceType.EARNINGS_CALL,
                title="ACME Q3 call",
                storage_uri="s3://x/b.mp3",
                checksum="b" * 64,
                fiscal_year=2025,
                fiscal_quarter=3,
            ),
        ]
    )
    await session.flush()


async def test_count_documents_tool(db_session: AsyncSession) -> None:
    await _seed(db_session)
    ctx = ToolContext(session=db_session)

    assert "2 document(s)" in await registry.call("count_documents", "{}", ctx)
    filtered = await registry.call("count_documents", '{"source_type": "xbrl"}', ctx)
    assert "0 document(s)" in filtered


async def test_count_documents_rejects_unknown_source_type(db_session: AsyncSession) -> None:
    ctx = ToolContext(session=db_session)
    result = await registry.call("count_documents", '{"source_type": "tweets"}', ctx)

    # The model must be told what the valid values are, not just that it failed.
    assert "unknown source_type" in result
    assert "sec_filing" in result


async def test_list_documents_tool(db_session: AsyncSession) -> None:
    await _seed(db_session)
    ctx = ToolContext(session=db_session)

    listed = await registry.call("list_documents", '{"limit": 10}', ctx)
    assert "ACME 10-K FY2025" in listed
    assert "FY2025 Q3" in listed

    empty = await registry.call("list_documents", '{"source_type": "xbrl"}', ctx)
    assert empty == "No documents match that filter."


async def test_ingestion_status_tool(db_session: AsyncSession) -> None:
    ctx = ToolContext(session=db_session)
    assert "No documents" in await registry.call("ingestion_status", "{}", ctx)

    await _seed(db_session)
    assert "2 pending" in await registry.call("ingestion_status", "{}", ctx)
