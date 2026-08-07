"""Aggregate router for API v1."""

from fastapi import APIRouter

from parallax.api.v1.routes import documents, health

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
