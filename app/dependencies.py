"""
FastAPI dependency injection.
"""
from typing import AsyncGenerator, Annotated
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.config import settings


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_actor(
    request: Request,
    x_actor_id: str = Header(default="local_operator"),
) -> str:
    """
    Returns the identity of the current actor.

    When auth_mode=NONE (default): always returns 'local_operator'.
    When auth_mode=GOOGLE_SSO: returns the verified user email.
    """
    if settings.auth_mode == "NONE":
        return "local_operator"
    # Phase 2: validate Google SSO token and return email
    return x_actor_id


ActorDep = Annotated[str, Depends(get_current_actor)]
