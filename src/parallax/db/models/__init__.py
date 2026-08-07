"""SQLAlchemy models. Import every model here so Alembic autogenerate sees them."""

from parallax.db.base import Base
from parallax.db.models.claim import Claim, ClaimProvenance, ClaimStatus, Modality
from parallax.db.models.document import Document, DocumentStatus, SourceType
from parallax.db.models.entity import Entity, EntityType

__all__ = [
    "Base",
    "Claim",
    "ClaimProvenance",
    "ClaimStatus",
    "Document",
    "DocumentStatus",
    "Entity",
    "EntityType",
    "Modality",
    "SourceType",
]
