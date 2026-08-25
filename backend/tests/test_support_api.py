"""The HTTP surface: /support/ask and /support/agents."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient

from parallax import __version__
from parallax.agents import computer as computer_agent
from parallax.agents import mobile as mobile_agent
from parallax.agents.supervisor import Supervisor
from parallax.api.v1.routes.support import get_supervisor

from fakes import FakeLLM, text_turn, tool_turn


def stub_supervisor(
    supervisor_turns: list, mobile_turns: list | None = None, computer_turns: list | None = None
) -> Supervisor:
    return Supervisor(
        llm=FakeLLM(supervisor_turns, model="supervisor-model"),
        mobile=mobile_agent.build(FakeLLM(mobile_turns or [], model="mobile-model")),
        computer=computer_agent.build(FakeLLM(computer_turns or [], model="computer-model")),
    )


async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["version"] == __version__


async def test_liveness_needs_no_dependencies(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_agents_endpoint_describes_the_system(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_supervisor] = lambda: stub_supervisor([])
    try:
        resp = await client.get("/api/v1/support/agents")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["supervisor"]["stages"] == ["route", "delegate", "review"]

    names = {s["name"] for s in body["specialists"]}
    assert names == {"mobile", "computer"}
    for specialist in body["specialists"]:
        assert len(specialist["tools"]) == 3


async def test_ask_returns_the_answer_and_the_full_trace(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_supervisor] = lambda: stub_supervisor(
        supervisor_turns=[text_turn("computer"), text_turn("Your warranty is active until 2027.")],
        computer_turns=[
            tool_turn("check_warranty", '{"serial_number": "5CD1234ABC"}'),
            text_turn("Active until 14 March 2027."),
        ],
    )
    try:
        resp = await client.post(
            "/api/v1/support/ask",
            json={"message": "is my laptop under warranty? serial 5CD1234ABC"},
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["answer"] == "Your warranty is active until 2027."
    assert body["route"]["agent"] == "computer"
    assert body["delegate"]["agent"] == "computer"
    assert body["delegate"]["answer"] == "Active until 14 March 2027."
    assert body["delegate"]["steps"][0]["tool"] == "check_warranty"
    assert body["review"]["changed"] is True
    assert body["stages"][0] == "route -> computer"


async def test_ask_omits_delegate_when_out_of_scope(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_supervisor] = lambda: stub_supervisor(
        supervisor_turns=[text_turn("none"), text_turn("We only cover phones and computers.")]
    )
    try:
        resp = await client.post("/api/v1/support/ask", json={"message": "book a flight"})
    finally:
        app.dependency_overrides.clear()

    body = resp.json()
    assert body["delegate"] is None
    assert body["route"]["agent"] == "none"


async def test_ask_rejects_an_empty_message(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/support/ask", json={"message": ""})
    assert resp.status_code == 422


async def test_openapi_is_served(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/support/ask" in resp.json()["paths"]
