"""Document registry endpoints.

Thin on purpose: these exist to prove the API <-> Postgres path end to end.
Ingestion itself is driven by the offline orchestrator, not by these routes.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from parallax.api.deps import SessionDep
from parallax.core.exceptions import ConflictError, NotFoundError
from parallax.db.models.document import Document, SourceType
from parallax.schemas.common import Page
from parallax.schemas.document import DocumentCreate, DocumentRead

router = APIRouter()


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def register_document(payload: DocumentCreate, session: SessionDep) -> Document:
    """Register a source artifact. `checksum` makes this idempotent per file."""
    document = Document(**payload.model_dump())
    session.add(document)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(
            "A document with this checksum is already registered",
            details={"checksum": payload.checksum},
        ) from exc
    await session.refresh(document)
    return document


@router.get("", response_model=Page[DocumentRead])
async def list_documents(
    session: SessionDep,
    source_type: SourceType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Page[DocumentRead]:
    where = [Document.source_type == source_type] if source_type else []

    total = await session.scalar(select(func.count()).select_from(Document).where(*where))
    rows = await session.scalars(
        select(Document)
        .where(*where)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return Page[DocumentRead](
        items=[DocumentRead.model_validate(r) for r in rows.all()],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: uuid.UUID, session: SessionDep) -> Document:
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found", details={"document_id": str(document_id)})
    return document
