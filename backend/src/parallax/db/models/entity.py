"""Companies and other named entities that claims are attributed to."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from parallax.db.base import Base, TimestampMixin, UUIDMixin, pg_enum

if TYPE_CHECKING:
    from parallax.db.models.claim import Claim
    from parallax.db.models.document import Document


class EntityType(enum.StrEnum):
    COMPANY = "company"
    SEGMENT = "segment"
    PRODUCT = "product"
    PERSON = "person"


class Entity(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "entities"

    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        pg_enum(EntityType, "entity_type"), nullable=False, default=EntityType.COMPANY
    )
    ticker: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    cik: Mapped[str | None] = mapped_column(String(16), nullable=True, unique=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")

    documents: Mapped[list[Document]] = relationship(back_populates="entity")
    claims: Mapped[list[Claim]] = relationship(back_populates="entity")

    def __repr__(self) -> str:
        return f"<Entity {self.name} ({self.ticker or self.entity_type.value})>"
