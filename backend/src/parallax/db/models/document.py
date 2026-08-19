"""Source artifacts fed into the ingestion pipeline."""

from __future__ import annotations

import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from parallax.db.base import Base, TimestampMixin, UUIDMixin, pg_enum

if TYPE_CHECKING:
    from parallax.db.models.claim import Claim
    from parallax.db.models.entity import Entity


class SourceType(enum.StrEnum):
    """One per ingestion branch in the offline pipeline."""

    SEC_FILING = "sec_filing"
    INVESTOR_DECK = "investor_deck"
    EARNINGS_CALL = "earnings_call"
    XBRL = "xbrl"


class DocumentStatus(enum.StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("checksum", name="uq_documents_checksum"),)

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[SourceType] = mapped_column(
        pg_enum(SourceType, "source_type"), nullable=False, index=True
    )
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Object key in MinIO; the bytes never live in Postgres.
    storage_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Audio only, seconds.
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)

    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")

    entity: Mapped[Entity | None] = relationship(back_populates="documents")
    claims: Mapped[list[Claim]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document {self.source_type.value} {self.title!r}>"
