"""Domain exceptions and their HTTP translation."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class ParallaxError(Exception):
    """Base class for all PARALLAX domain errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ParallaxError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(ParallaxError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(ParallaxError):
    # Literal rather than the starlette constant, which was renamed in 0.47.
    status_code = 422
    code = "validation_error"


class DependencyUnavailableError(ParallaxError):
    """A backing service (DB, Qdrant, MinIO, LLM) is unreachable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "dependency_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ParallaxError)
    async def _handle(_: Request, exc: ParallaxError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
