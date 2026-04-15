"""
Account — the DACA clearing account.
Only CHECKING accounts supported — DACAs cannot be set up on Treasury or Prime Treasury accounts.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    daca_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("daca_requests.id"), nullable=False, index=True
    )

    # Only CHECKING is supported per Rho DACA policy
    account_type: Mapped[str] = mapped_column(String(50), default="CHECKING")

    # Account number stored encrypted — use utils/encryption.py
    account_number_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    routing_number: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Rho internal references
    rho_tenet_account_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rap_account_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Account lifecycle
    is_new_account: Mapped[bool] = mapped_column(Boolean, default=True)
    # True = new clearing account; False = converted from existing deposit account
    eng_ticket_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # ENG ticket for account conversion (e.g. ENG-35904)

    # Status in RAP
    account_status: Mapped[str] = mapped_column(String(50), default="PENDING_SETUP")
    # PENDING_SETUP | ACTIVE | DEACTIVATED | RESTRICTED | BLOCKED | CLOSED

    # Control status
    control_status: Mapped[str] = mapped_column(String(50), default="BORROWER_CONTROL")
    # BORROWER_CONTROL | LENDER_CONTROL

    # Deactivation tracking (account deactivated while awaiting DocuSign, per SOP)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lender external bank details (for trigger event / sweep setup)
    # Encrypted storage
    lender_ach_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    lender_ach_routing: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lender_wire_account_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    lender_wire_routing: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Sweep configuration (set to DAILY after trigger event, amount=0)
    sweep_cadence: Mapped[str] = mapped_column(String(20), default="NEVER")
    # NEVER | DAILY

    # Relationships
    daca_request: Mapped["DacaRequest"] = relationship(  # type: ignore[name-defined]
        "DacaRequest", back_populates="accounts"
    )
    trigger_events: Mapped[list["TriggerEvent"]] = relationship(  # type: ignore[name-defined]
        "TriggerEvent", back_populates="account"
    )

    def __repr__(self) -> str:
        return f"<Account {self.id}: {self.account_status} / {self.control_status}>"
