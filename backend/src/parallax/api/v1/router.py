"""Aggregate router for API v1."""

from fastapi import APIRouter

from parallax.api.v1.routes import health, support

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(support.router, prefix="/support", tags=["support"])
