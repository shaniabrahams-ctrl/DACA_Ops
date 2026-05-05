"""
Notification Channels API — manages the Slack channel(s) that receive DACA alerts.

For now we use a single channel for ALL alert types (email alerts, SLA alerts,
trigger events, weekly updates, activity). Per Shani: only #daca-ops is in use.
"""
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import SessionDep, ActorDep
from app.models.notification_channel import NotificationChannel, NotificationType

router = APIRouter()


ALL_NOTIFICATION_TYPES = [
    NotificationType.EMAIL_ALERT,
    NotificationType.WEEKLY_UPDATE,
    NotificationType.SLA_ALERT,
    NotificationType.TRIGGER_EVENT,
    NotificationType.ACTIVITY,
]


class NotificationChannelOut(BaseModel):
    channel_id: str
    channel_name: str
    notification_types: list[str]
    enabled: bool
    updated_by: str | None
    updated_at: datetime | None


class NotificationChannelUpdate(BaseModel):
    channel_id: str           # Slack channel ID (e.g. "C0APFKNF8SY")
    channel_name: str         # Human-friendly name (e.g. "daca-ops")
    enabled: bool = True


@router.get("", response_model=NotificationChannelOut)
async def get_primary_channel(db: SessionDep):
    """
    Returns the current primary Slack channel used for ALL DACA notifications.
    If no row exists yet, returns sensible defaults from settings.
    """
    from app.config import settings

    result = await db.execute(
        select(NotificationChannel).limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        return NotificationChannelOut(
            channel_id=settings.slack_daca_ops_channel_id or "",
            channel_name="daca-ops",
            notification_types=ALL_NOTIFICATION_TYPES,
            enabled=False,
            updated_by=None,
            updated_at=None,
        )

    return NotificationChannelOut(
        channel_id=row.channel_id,
        channel_name=row.channel_name,
        notification_types=ALL_NOTIFICATION_TYPES,
        enabled=row.enabled,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@router.put("", response_model=NotificationChannelOut)
async def update_primary_channel(
    body: NotificationChannelUpdate,
    db: SessionDep,
    actor: ActorDep,
):
    """
    Set the primary Slack channel for ALL DACA notifications.

    Implementation: writes one NotificationChannel row per notification type
    (so the existing notification_service queries pick it up), all pointing
    to the same channel_id.
    """
    # Wipe existing rows and replace
    existing_result = await db.execute(select(NotificationChannel))
    for row in existing_result.scalars().all():
        await db.delete(row)
    await db.flush()

    for ntype in ALL_NOTIFICATION_TYPES:
        db.add(NotificationChannel(
            channel_id=body.channel_id,
            channel_name=body.channel_name,
            notification_type=ntype,
            enabled=body.enabled,
            updated_by=actor,
        ))
    await db.flush()

    return NotificationChannelOut(
        channel_id=body.channel_id,
        channel_name=body.channel_name,
        notification_types=ALL_NOTIFICATION_TYPES,
        enabled=body.enabled,
        updated_by=actor,
        updated_at=datetime.utcnow(),
    )
