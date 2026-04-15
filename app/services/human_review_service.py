"""
Human Review Service — manages the review queue.

When oversight gate returns PAUSE, a HumanReviewItem is created.
Reviewers approve/reject/return via the API, which unblocks state transitions.
"""
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.human_review import HumanReviewItem
from app.models.audit_log import ActorType
from app.services import audit_service


async def create_review_item(
    db: AsyncSession,
    *,
    daca_request_id: uuid.UUID,
    stage: str,
    review_type: str,
    payload: dict[str, Any] | None = None,
    agent_recommendation: str | None = None,
    agent_confidence: float | None = None,
    agent_name: str | None = None,
    assigned_to: str | None = None,
    sla_deadline: datetime | None = None,
) -> HumanReviewItem:
    item = HumanReviewItem(
        daca_request_id=daca_request_id,
        stage=stage,
        review_type=review_type,
        payload=payload,
        agent_recommendation=agent_recommendation,
        agent_confidence=agent_confidence,
        agent_name=agent_name,
        assigned_to=assigned_to,
        sla_deadline=sla_deadline,
    )
    db.add(item)
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="HumanReviewItem",
        entity_id=item.id,
        action="review_item_created",
        actor_type=ActorType.SYSTEM,
        actor_id="system",
        daca_request_id=daca_request_id,
        after_state={"stage": stage, "review_type": review_type},
        rationale=f"Paused at {stage} — awaiting human review",
    )
    return item


async def approve(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    actor_id: str,
    notes: str | None = None,
) -> HumanReviewItem:
    item = await _get_item(db, item_id)
    item.status = "APPROVED"
    item.reviewed_by = actor_id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = notes
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="HumanReviewItem",
        entity_id=item.id,
        action="review_approved",
        actor_type=ActorType.HUMAN,
        actor_id=actor_id,
        daca_request_id=item.daca_request_id,
        before_state={"status": "PENDING"},
        after_state={"status": "APPROVED"},
        rationale=notes,
    )
    return item


async def reject(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    actor_id: str,
    notes: str | None = None,
) -> HumanReviewItem:
    item = await _get_item(db, item_id)
    item.status = "REJECTED"
    item.reviewed_by = actor_id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = notes
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="HumanReviewItem",
        entity_id=item.id,
        action="review_rejected",
        actor_type=ActorType.HUMAN,
        actor_id=actor_id,
        daca_request_id=item.daca_request_id,
        before_state={"status": "PENDING"},
        after_state={"status": "REJECTED"},
        rationale=notes,
    )
    return item


async def return_for_revision(
    db: AsyncSession,
    *,
    item_id: uuid.UUID,
    actor_id: str,
    notes: str | None = None,
) -> HumanReviewItem:
    item = await _get_item(db, item_id)
    item.status = "RETURNED_FOR_REVISION"
    item.reviewed_by = actor_id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_notes = notes
    await db.flush()

    await audit_service.log_event(
        db,
        entity_type="HumanReviewItem",
        entity_id=item.id,
        action="review_returned",
        actor_type=ActorType.HUMAN,
        actor_id=actor_id,
        daca_request_id=item.daca_request_id,
        before_state={"status": "PENDING"},
        after_state={"status": "RETURNED_FOR_REVISION"},
        rationale=notes,
    )
    return item


async def get_queue(
    db: AsyncSession,
    *,
    status: str | None = "PENDING",
    stage: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[HumanReviewItem]:
    q = select(HumanReviewItem)
    if status:
        q = q.where(HumanReviewItem.status == status)
    if stage:
        q = q.where(HumanReviewItem.stage == stage)
    q = q.order_by(HumanReviewItem.created_at.asc()).offset(offset).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def _get_item(db: AsyncSession, item_id: uuid.UUID) -> HumanReviewItem:
    result = await db.execute(select(HumanReviewItem).where(HumanReviewItem.id == item_id))
    item = result.scalar_one_or_none()
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Review item not found")
    return item
