"""
Core state machine for DacaRequest status transitions.

Transition flow:
  1. Validate target_status is allowed from current status
  2. Check oversight gate (always_human or mode check)
  3. If PAUSE → create HumanReviewItem, do NOT transition
  4. If PROCEED → update status, calculate SLA, persist
  5. Create immutable AuditLog entry
  6. Dispatch next agent task via Celery (TODO: Sprint 3)
"""
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.audit_log import ActorType
from app.services import audit_service, oversight_service, human_review_service
from app.services.oversight_service import GateDecision


# State machine definition:
# stage → {next: [...allowed next states], sla_hours: int | None}
TRANSITIONS: dict[str, dict] = {
    DacaRequestStatus.FRAUD_INITIAL_REVIEW: {
        "next": [DacaRequestStatus.TYPEFORM_SENT, DacaRequestStatus.CANCELLED],
        "sla_hours": 4,
    },
    DacaRequestStatus.TYPEFORM_SENT: {
        "next": [
            DacaRequestStatus.LEGAL_REDLINE_REVIEW,
            DacaRequestStatus.PENDING_COMPLIANCE_ASSEMBLY,
            DacaRequestStatus.ON_HOLD,
            DacaRequestStatus.CANCELLED,
        ],
        "sla_hours": 72,
    },
    DacaRequestStatus.LEGAL_REDLINE_REVIEW: {
        "next": [
            DacaRequestStatus.TEMPLATES_AGREEMENTS_SENT,
            DacaRequestStatus.CANCELLED,
            DacaRequestStatus.ON_HOLD,
        ],
        "sla_hours": 48,
    },
    DacaRequestStatus.TEMPLATES_AGREEMENTS_SENT: {
        "next": [
            DacaRequestStatus.PENDING_COMPLIANCE_ASSEMBLY,
            DacaRequestStatus.LEGAL_REDLINE_REVIEW,
            DacaRequestStatus.ON_HOLD,
            DacaRequestStatus.CANCELLED,
        ],
        "sla_hours": None,
    },
    DacaRequestStatus.PENDING_COMPLIANCE_ASSEMBLY: {
        "next": [
            DacaRequestStatus.PRE_WEBSTER_REVIEW,
            DacaRequestStatus.ON_HOLD,
            DacaRequestStatus.CANCELLED,
        ],
        "sla_hours": 48,
    },
    DacaRequestStatus.PRE_WEBSTER_REVIEW: {
        "next": [
            DacaRequestStatus.DOCUSIGN_SENT,
            DacaRequestStatus.PENDING_COMPLIANCE_ASSEMBLY,
            DacaRequestStatus.ON_HOLD,
            DacaRequestStatus.CANCELLED,
        ],
        "sla_hours": 24,
    },
    DacaRequestStatus.DOCUSIGN_SENT: {
        "next": [
            DacaRequestStatus.PENDING_FINAL_SETUP,
            DacaRequestStatus.ON_HOLD,
            DacaRequestStatus.CANCELLED,
        ],
        "sla_hours": 168,  # 7 days
    },
    DacaRequestStatus.PENDING_FINAL_SETUP: {
        "next": [
            DacaRequestStatus.DONE,
            DacaRequestStatus.ON_HOLD,
            DacaRequestStatus.CANCELLED,
        ],
        "sla_hours": 48,
    },
    DacaRequestStatus.DONE: {
        "next": [
            DacaRequestStatus.TRIGGERED,
            DacaRequestStatus.TERMINATED,
        ],
        "sla_hours": None,
    },
    DacaRequestStatus.TRIGGERED: {
        "next": [
            DacaRequestStatus.DONE,
            DacaRequestStatus.TERMINATED,
        ],
        "sla_hours": 2,
    },
    DacaRequestStatus.ON_HOLD: {
        "next": DacaRequestStatus.ALL_STATUSES,  # can resume to any status
        "sla_hours": None,
    },
    DacaRequestStatus.TERMINATED: {"next": [], "sla_hours": None},
    DacaRequestStatus.CANCELLED: {"next": [], "sla_hours": None},
}


async def transition(
    db: AsyncSession,
    *,
    daca_request_id: uuid.UUID,
    target_status: str,
    actor_type: str,
    actor_id: str,
    rationale: str | None = None,
    confidence: float = 1.0,
    ip_address: str | None = None,
) -> DacaRequest:
    """
    Attempt a state transition. Returns the (possibly unchanged) DacaRequest.
    If the gate says PAUSE, a HumanReviewItem is created and status is unchanged.
    If the gate says PROCEED, status is updated.
    """
    # 1. Load the request
    result = await db.execute(select(DacaRequest).where(DacaRequest.id == daca_request_id))
    request = result.scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="DACA request not found")

    current_status = request.status

    # 2. Validate the target is an allowed next state
    allowed = TRANSITIONS.get(current_status, {}).get("next", [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{current_status}' to '{target_status}'. "
                   f"Allowed: {allowed}",
        )

    # 3. Check oversight gate
    gate_decision, gate_reason = await oversight_service.check_gate(
        db, stage=target_status, confidence=confidence
    )

    if gate_decision == GateDecision.PAUSE:
        # Create a HumanReviewItem — operator will approve to proceed
        await human_review_service.create_review_item(
            db,
            daca_request_id=daca_request_id,
            stage=target_status,
            review_type="GATE_APPROVAL",
            payload={
                "from_status": current_status,
                "to_status": target_status,
                "rationale": rationale,
                "gate_reason": gate_reason,
            },
            agent_recommendation=rationale,
            agent_confidence=confidence,
            agent_name=actor_id if actor_type == ActorType.AGENT else None,
        )
        await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=daca_request_id,
            action="transition_paused",
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            daca_request_id=daca_request_id,
            before_state={"status": current_status},
            after_state={"status": current_status, "pending_transition": target_status},
            rationale=gate_reason,
            ip_address=ip_address,
        )
        return request

    # 4. PROCEED — perform the transition
    sla_hours = TRANSITIONS.get(target_status, {}).get("sla_hours")
    new_deadline: datetime | None = None
    if sla_hours is not None:
        new_deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

    request.previous_status = current_status
    request.status = target_status
    request.sla_deadline = new_deadline
    await db.flush()

    # 5. Immutable audit log
    await audit_service.log_status_change(
        db,
        daca_request_id=daca_request_id,
        from_status=current_status,
        to_status=target_status,
        actor_type=actor_type,
        actor_id=actor_id,
        rationale=f"{rationale or ''} | Gate: {gate_reason}".strip(" |"),
        ip_address=ip_address,
    )

    # 6. TODO Sprint 3: dispatch next agent task via Celery

    return request
