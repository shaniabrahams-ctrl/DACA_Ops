"""
Notification Service — sends Slack messages for various event types.

All messages go to #daca-ops (C0APFKNF8SY) by default.
Channel routing is controlled by the NotificationChannel table.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notification_channel import NotificationChannel, NotificationType
from app.config import settings

logger = logging.getLogger(__name__)


async def _get_enabled_channels(
    db: AsyncSession, notification_type: str
) -> list[str]:
    """Returns list of channel IDs that have this notification type enabled."""
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.notification_type == notification_type,
            NotificationChannel.enabled == True,  # noqa: E712
        )
    )
    return [nc.channel_id for nc in result.scalars().all()]


async def send_email_alert(
    db: AsyncSession,
    *,
    subject: str,
    sender: str,
    snippet: str,
    thread_url: str | None = None,
    external_ref: str | None = None,
) -> None:
    """
    Sends a Slack notification when a new email arrives at daca@rho.co.
    Uses Block Kit for rich formatting.
    """
    from app.integrations import slack as slack_integration

    channels = await _get_enabled_channels(db, NotificationType.EMAIL_ALERT)
    if not channels:
        channels = [settings.slack_daca_ops_channel_id]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": ":envelope: New Email to daca@rho.co"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*From:*\n{sender}"},
                {"type": "mrkdwn", "text": f"*Subject:*\n{subject}"},
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"_{snippet[:200]}_"},
        },
    ]

    actions: list[dict] = []
    if thread_url:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open in Gmail"},
            "url": thread_url,
        })
    if external_ref:
        actions.append({
            "type": "button",
            "text": {"type": "plain_text", "text": f"View {external_ref}"},
            "action_id": f"view_{external_ref}",
        })
    if actions:
        blocks.append({"type": "actions", "elements": actions})

    for channel_id in channels:
        try:
            await slack_integration.send_blocks(channel_id=channel_id, blocks=blocks)
        except Exception as exc:
            logger.warning("Slack email alert failed for channel %s: %s", channel_id, exc)


async def send_sla_alert(
    db: AsyncSession,
    *,
    external_ref: str,
    status: str,
    severity: str,  # WARNING | CRITICAL
    hours_remaining: float,
    assigned_to: str | None = None,
) -> None:
    from app.integrations import slack as slack_integration

    channels = await _get_enabled_channels(db, NotificationType.SLA_ALERT)
    if not channels:
        channels = [settings.slack_daca_ops_channel_id]

    emoji = ":warning:" if severity == "WARNING" else ":rotating_light:"
    mention = f" (assigned to {assigned_to})" if assigned_to else ""

    text = (
        f"{emoji} *SLA {severity}* — {external_ref} is at status *{status}*{mention}\n"
        f"{'Time remaining' if hours_remaining > 0 else 'Overdue by'}: "
        f"*{abs(hours_remaining):.1f} hours*"
    )

    for channel_id in channels:
        try:
            await slack_integration.send_message(channel_id=channel_id, text=text)
        except Exception as exc:
            logger.warning("Slack SLA alert failed for channel %s: %s", channel_id, exc)


async def send_activity(
    db: AsyncSession,
    *,
    external_ref: str,
    action: str,
    actor: str,
    details: str | None = None,
) -> None:
    """Posts to the activity feed channel."""
    from app.integrations import slack as slack_integration

    channels = await _get_enabled_channels(db, NotificationType.ACTIVITY)
    if not channels:
        return  # Activity feed is opt-in

    text = f":memo: *{external_ref}* — {action} by {actor}"
    if details:
        text += f"\n{details}"

    for channel_id in channels:
        try:
            await slack_integration.send_message(channel_id=channel_id, text=text)
        except Exception as exc:
            logger.warning("Slack activity post failed for channel %s: %s", channel_id, exc)
