"""Normalized claims and the provenance that anchors each one to its source."""

from __future__ import annotations

import enum
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from parallax.core.config import settings
from parallax.db.base import Base, TimestampMixin, UUIDMixin, pg_enum

if TYPE_CHECKING:
    from parallax.db.models.document import Document
    from parallax.db.models.entity import Entity


class Modality(enum.StrEnum):
    """Which agent lane produced the claim."""

    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    AUDIO = "audio"
    STRUCTURED = "structured"


class ClaimStatus(enum.StrEnum):
    EXTRACTED = "extracted"
    NORMALIZED = "normalized"
    MERGED = "merged"
    SUPERSEDED = "superseded"


class Claim(UUIDMixin, TimestampMixin, Base):
    """A single assertion of a metric value, normalized to a comparable form.

    `canonical_key` is what the reconciliation engine groups on: the same key
    across two modalities means the values must agree.
    """

    __tablename__ = "claims"
    __table_args__ = (
        Index("ix_claims_canonical_key_period", "canonical_key", "period_end"),
        Index("ix_claims_entity_metric", "entity_id", "metric"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    # Set when this claim was merged into another; the survivor keeps the key.
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL"), nullable=True
    )

    modality: Mapped[Modality] = mapped_column(
        pg_enum(Modality, "modality"), nullable=False, index=True
    )
    status: Mapped[ClaimStatus] = mapped_column(
        pg_enum(ClaimStatus, "claim_status"), nullable=False, default=ClaimStatus.EXTRACTED
    )

    canonical_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(255), nullable=False)
    # XBRL tag when the claim came from (or was aligned to) structured facts.
    xbrl_concept: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 6), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Power of ten already applied to `value` (6 = millions), kept for display.
    scale: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )

    document: Mapped[Document] = relationship(back_populates="claims")
    entity: Mapped[Entity | None] = relationship(back_populates="claims")
    provenance: Mapped[list[ClaimProvenance]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Claim {self.canonical_key}={self.value} {self.unit or ''}>"


class ClaimProvenance(UUIDMixin, TimestampMixin, Base):
    """Where a claim came from, precisely enough to render evidence.

    `locator` carries the modality-specific anchor: page + bbox for PDFs,
    start/end seconds for audio, cell coordinates for tables, context ref
    for XBRL.
    """

    __tablename__ = "claim_provenance"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    extractor: Mapped[str] = mapped_column(String(128), nullable=False)
    extractor_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    claim: Mapped[Claim] = relationship(back_populates="provenance")

    def __repr__(self) -> str:
        return f"<ClaimProvenance claim={self.claim_id} via={self.extractor}>"
