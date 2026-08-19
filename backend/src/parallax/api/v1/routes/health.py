"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from parallax import __version__
from parallax.api.deps import SessionDep
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
async def ready(session: SessionDep) -> dict[str, object]:
    """Process is up *and* Postgres answers."""
    checks: dict[str, str] = {}
    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:
        log.error("readiness_check_failed", dependency="postgres", error=str(exc))
        raise DependencyUnavailableError(
            "PostgreSQL is not reachable", details={"postgres": "unavailable"}
        ) from exc

    return {"status": "ok", "version": __version__, "checks": checks}
