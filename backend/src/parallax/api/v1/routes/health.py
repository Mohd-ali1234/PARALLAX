"""Liveness and readiness probes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, status

from parallax import __version__
from parallax.core.config import settings
from parallax.core.exceptions import DependencyUnavailableError
from parallax.core.logging import get_logger

router = APIRouter()
log = get_logger(__name__)


@router.get("/live", status_code=status.HTTP_200_OK, summary="Liveness probe")
async def live() -> dict[str, str]:
    """Process is up. Does not touch any dependency."""
    return {"status": "ok", "version": __version__, "env": settings.env}


@router.get("/ready", status_code=status.HTTP_200_OK, summary="Readiness probe")
async def ready() -> dict[str, object]:
    """Process is up *and* the model server answers.

    The LLM is the only hard dependency: with it down, every agent fails.
    """
    url = settings.llm_base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {settings.llm_api_key}"}
            )
        response.raise_for_status()
    except Exception as exc:
        log.error("readiness_check_failed", dependency="llm", error=str(exc))
        raise DependencyUnavailableError(
            f"LLM server at {settings.llm_base_url} is not reachable",
            details={"llm": "unavailable", "base_url": settings.llm_base_url},
        ) from exc

    return {
        "status": "ok",
        "version": __version__,
        "checks": {"llm": "ok"},
        "model": settings.llm_model,
    }
