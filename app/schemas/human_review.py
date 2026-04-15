"""
Pydantic schemas for HumanReviewItem.
"""
import uuid
from typing import Any
from datetime import datetime
from pydantic import BaseModel


class HumanReviewCreate(BaseModel):
    daca_request_id: uuid.UUID
    stage: str
    review_type: str
    payload: dict[str, Any] | None = None
    agent_recommendation: str | None = None
    agent_confidence: float | None = None
    agent_name: str | None = None
    assigned_to: str | None = None
    sla_deadline: datetime | None = None


class ReviewDecision(BaseModel):
    notes: str | None = None


class HumanReviewOut(BaseModel):
    id: uuid.UUID
    daca_request_id: uuid.UUID
    stage: str
    review_type: str
    payload: dict[str, Any] | None
    agent_recommendation: str | None
    agent_confidence: float | None
    agent_name: str | None
    status: str
    assigned_to: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    sla_deadline: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
