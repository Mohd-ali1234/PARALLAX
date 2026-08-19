"""Document request/response models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from parallax.db.models.document import DocumentStatus, SourceType


class DocumentCreate(BaseModel):
    entity_id: uuid.UUID | None = None
    source_type: SourceType
    title: str = Field(min_length=1, max_length=1024)
    storage_uri: str = Field(min_length=1, max_length=2048)
    checksum: str = Field(min_length=8, max_length=64)
    mime_type: str | None = None
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    fiscal_quarter: int | None = Field(default=None, ge=1, le=4)
    period_start: date | None = None
    period_end: date | None = None
    published_at: date | None = None
    doc_metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_id: uuid.UUID | None
    source_type: SourceType
    status: DocumentStatus
    title: str
    storage_uri: str
    checksum: str
    mime_type: str | None
    page_count: int | None
    duration_s: int | None
    fiscal_year: int | None
    fiscal_quarter: int | None
    period_start: date | None
    period_end: date | None
    published_at: date | None
    error: str | None
    doc_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
