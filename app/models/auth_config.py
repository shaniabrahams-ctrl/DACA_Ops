"""
AuthConfig — authentication mode toggle.
Default: NONE (no login required, all actions logged as 'local_operator').
When GOOGLE_SSO: individual identity tracked, RBAC enforced.
"""
import uuid
from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin


class AuthMode:
    NONE = "NONE"           # Default: no authentication required
    GOOGLE_SSO = "GOOGLE_SSO"


class AuthConfig(Base, TimestampMixin):
    __tablename__ = "auth_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    auth_mode: Mapped[str] = mapped_column(String(20), nullable=False, default=AuthMode.NONE)
    # AuthMode.NONE | AuthMode.GOOGLE_SSO

    # When auth=NONE: all actions logged as "local_operator"
    # When auth=GOOGLE_SSO: actions logged with individual @rho.co email
    allowed_domain: Mapped[str] = mapped_column(String(100), default="rho.co")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
