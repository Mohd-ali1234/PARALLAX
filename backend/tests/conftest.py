"""Test fixtures.

No test needs a model server: every LLM call is stubbed. That keeps the suite
runnable anywhere, and means what is under test is the pipeline, not the model.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from parallax.main import create_app
from parallax.tools.base import ToolContext


@pytest.fixture(scope="session")
def app() -> FastAPI:
    return create_app()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def ctx() -> ToolContext:
    return ToolContext(request_id="test-request")
