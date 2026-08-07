from __future__ import annotations

from httpx import AsyncClient

PAYLOAD = {
    "source_type": "sec_filing",
    "title": "ACME Corp 10-K FY2025",
    "storage_uri": "s3://parallax-artifacts/acme/10k-2025.pdf",
    "checksum": "a" * 64,
    "mime_type": "application/pdf",
    "fiscal_year": 2025,
}


async def test_register_and_fetch_document(db_client: AsyncClient) -> None:
    created = await db_client.post("/api/v1/documents", json=PAYLOAD)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "pending"
    assert body["source_type"] == "sec_filing"

    fetched = await db_client.get(f"/api/v1/documents/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == PAYLOAD["title"]


async def test_duplicate_checksum_conflicts(db_client: AsyncClient) -> None:
    assert (await db_client.post("/api/v1/documents", json=PAYLOAD)).status_code == 201
    dup = await db_client.post("/api/v1/documents", json={**PAYLOAD, "title": "same file"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"


async def test_list_filters_by_source_type(db_client: AsyncClient) -> None:
    await db_client.post("/api/v1/documents", json=PAYLOAD)
    await db_client.post(
        "/api/v1/documents",
        json={**PAYLOAD, "source_type": "earnings_call", "checksum": "b" * 64},
    )

    listed = await db_client.get("/api/v1/documents", params={"source_type": "xbrl"})
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    listed = await db_client.get("/api/v1/documents", params={"source_type": "earnings_call"})
    assert listed.json()["total"] == 1


async def test_missing_document_is_404(db_client: AsyncClient) -> None:
    resp = await db_client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
