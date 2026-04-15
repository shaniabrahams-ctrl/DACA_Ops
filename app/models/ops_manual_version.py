"""
OpsManualVersion — tracks which version of the DACA Operations Manual is current.
Drive folder: 1uB1PnEMnGhrrvDzO-jZXnwVYKBfr0I8C
Polled weekly (Mondays) for new/updated files.
Referenced by AuditLog to show which SOP governed each decision.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin


class OpsManualVersion(Base, TimestampMixin):
    __tablename__ = "ops_manual_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    drive_file_id: Mapped[str] = mapped_column(String(200), nullable=False)
    drive_folder_id: Mapped[str] = mapped_column(
        String(200), default="1uB1PnEMnGhrrvDzO-jZXnwVYKBfr0I8C"
    )
    drive_file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    version_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # e.g. "DACA Operations Manual v2.1"

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Only one row should have is_current=True at any time
