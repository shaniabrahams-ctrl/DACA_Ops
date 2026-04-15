"""
NotificationChannel — configurable toggle per Slack channel per notification type.
Allows operator to control which channels receive which updates.
"""
import uuid
from sqlalchemy import String, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin


class NotificationType:
    EMAIL_ALERT = "EMAIL_ALERT"          # New email to daca@rho.co
    WEEKLY_UPDATE = "WEEKLY_UPDATE"      # Tuesday 10 AM ET status update
    SLA_ALERT = "SLA_ALERT"             # SLA warning/critical
    TRIGGER_EVENT = "TRIGGER_EVENT"     # Springing trigger alert
    ACTIVITY = "ACTIVITY"               # General activity feed


class NotificationChannel(Base, TimestampMixin):
    __tablename__ = "notification_channels"
    __table_args__ = (
        UniqueConstraint("channel_id", "notification_type", name="uq_channel_notif_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    channel_id: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "C0APFKNF8SY" for #daca-ops
    channel_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "#daca-ops"

    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # NotificationType constants

    enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
