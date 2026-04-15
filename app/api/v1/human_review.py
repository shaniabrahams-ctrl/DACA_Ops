"""
Human Review Queue API.
"""
import uuid
from fastapi import APIRouter, Query, Request

from app.dependencies import SessionDep, ActorDep
from app.schemas.human_review import HumanReviewOut, ReviewDecision
from app.services import human_review_service

router = APIRouter()


@router.get("", response_model=list[HumanReviewOut])
async def get_review_queue(
    db: SessionDep,
    status: str | None = Query(default="PENDING"),
    stage: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await human_review_service.get_queue(
        db, status=status, stage=stage, limit=limit, offset=offset
    )


@router.post("/{item_id}/approve", response_model=HumanReviewOut)
async def approve_review(
    item_id: uuid.UUID,
    body: ReviewDecision,
    db: SessionDep,
    actor: ActorDep,
    request: Request,
):
    """
    Approve a pending review item. The next call to transition() for this
    DACA request will then succeed (if gate allows).
    """
    item = await human_review_service.approve(
        db, item_id=item_id, actor_id=actor, notes=body.notes
    )
    return item


@router.post("/{item_id}/reject", response_model=HumanReviewOut)
async def reject_review(
    item_id: uuid.UUID,
    body: ReviewDecision,
    db: SessionDep,
    actor: ActorDep,
):
    item = await human_review_service.reject(
        db, item_id=item_id, actor_id=actor, notes=body.notes
    )
    return item


@router.post("/{item_id}/return", response_model=HumanReviewOut)
async def return_for_revision(
    item_id: uuid.UUID,
    body: ReviewDecision,
    db: SessionDep,
    actor: ActorDep,
):
    item = await human_review_service.return_for_revision(
        db, item_id=item_id, actor_id=actor, notes=body.notes
    )
    return item
