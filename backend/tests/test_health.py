from __future__ import annotations

from httpx import AsyncClient

from parallax import __version__


async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "PARALLAX"


async def test_liveness_needs_no_dependencies(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": __version__, "env": "local"}


async def test_readiness_reports_postgres(db_client: AsyncClient) -> None:
    resp = await db_client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["postgres"] == "ok"


async def test_openapi_is_served(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/documents" in resp.json()["paths"]
