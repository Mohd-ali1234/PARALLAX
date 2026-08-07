"""Initial schema: entities, documents, claims, claim provenance.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Pinned literal: BGE-M3 output width. Changing PARALLAX_EMBEDDING_DIM requires
# a new migration, not an edit to this one.
EMBEDDING_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- entities ---------------------------------------------------------
    op.create_table(
        "entities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column(
            "entity_type",
            sa.Enum("company", "segment", "product", "person", name="entity_type"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("cik", sa.String(length=16), nullable=True),
        sa.Column(
            "aliases", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_entities"),
        sa.UniqueConstraint("cik", name="uq_entities_cik"),
    )
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_ticker", "entities", ["ticker"])

    # --- documents --------------------------------------------------------
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum("sec_filing", "investor_deck", "earnings_call", "xbrl", name="source_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "parsing", "extracting", "indexed", "failed", name="document_status"
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("storage_uri", sa.String(length=2048), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "doc_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            name="fk_documents_entity_id_entities",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("checksum", name="uq_documents_checksum"),
    )
    op.create_index("ix_documents_entity_id", "documents", ["entity_id"])
    op.create_index("ix_documents_source_type", "documents", ["source_type"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_fiscal_year", "documents", ["fiscal_year"])

    # --- claims -----------------------------------------------------------
    op.create_table(
        "claims",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merged_into_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "modality",
            sa.Enum("text", "table", "chart", "audio", "structured", name="modality"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("extracted", "normalized", "merged", "superseded", name="claim_status"),
            nullable=False,
        ),
        sa.Column("canonical_key", sa.String(length=512), nullable=False),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("xbrl_concept", sa.String(length=255), nullable=True),
        sa.Column("value", sa.Numeric(precision=30, scale=6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("scale", sa.SmallInteger(), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "normalized", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claims"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_claims_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"], ["entities.id"], name="fk_claims_entity_id_entities", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["claims.id"],
            name="fk_claims_merged_into_id_claims",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_claims_document_id", "claims", ["document_id"])
    op.create_index("ix_claims_modality", "claims", ["modality"])
    op.create_index("ix_claims_canonical_key", "claims", ["canonical_key"])
    op.create_index("ix_claims_xbrl_concept", "claims", ["xbrl_concept"])
    op.create_index("ix_claims_period_end", "claims", ["period_end"])
    op.create_index("ix_claims_canonical_key_period", "claims", ["canonical_key", "period_end"])
    op.create_index("ix_claims_entity_metric", "claims", ["entity_id", "metric"])
    # ANN index for semantic claim lookup when pgvector is the search backend.
    op.execute(
        "CREATE INDEX ix_claims_embedding_hnsw ON claims "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )

    # --- claim_provenance -------------------------------------------------
    op.create_table(
        "claim_provenance",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "locator", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("extractor", sa.String(length=128), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claim_provenance"),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
            name="fk_claim_provenance_claim_id_claims",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_claim_provenance_claim_id", "claim_provenance", ["claim_id"])


def downgrade() -> None:
    op.drop_table("claim_provenance")
    op.execute("DROP INDEX IF EXISTS ix_claims_embedding_hnsw")
    op.drop_table("claims")
    op.drop_table("documents")
    op.drop_table("entities")
    for enum_name in ("claim_status", "modality", "document_status", "source_type", "entity_type"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
