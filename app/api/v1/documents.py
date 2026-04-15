"""
Documents API.
"""
import uuid
from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.document import Document
from app.models.audit_log import ActorType
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentOut
from app.services import audit_service

router = APIRouter()


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(
    body: DocumentCreate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    doc = Document(**body.model_dump())
    db.add(doc)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Document",
        entity_id=doc.id,
        action="document_uploaded",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=doc.daca_request_id,
        after_state={"document_type": doc.document_type, "file_name": doc.file_name},
        ip_address=request.client.host if request.client else None,
    )
    return doc


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    db: SessionDep,
    daca_request_id: uuid.UUID | None = Query(default=None),
    document_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = select(Document)
    if daca_request_id:
        q = q.where(Document.daca_request_id == daca_request_id)
    if document_type:
        q = q.where(Document.document_type == document_type)
    q = q.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, db: SessionDep):
    from fastapi import HTTPException
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(
    document_id: uuid.UUID,
    body: DocumentUpdate,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    from fastapi import HTTPException
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(doc, field, value)
    await db.flush()
    await audit_service.log_event(
        db,
        entity_type="Document",
        entity_id=doc.id,
        action="document_updated",
        actor_type=ActorType.HUMAN,
        actor_id=actor,
        daca_request_id=doc.daca_request_id,
        after_state=updates,
        ip_address=request.client.host if request.client else None,
    )
    return doc
