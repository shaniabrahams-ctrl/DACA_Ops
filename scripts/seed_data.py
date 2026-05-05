"""
Seed script — only inserts structural defaults that the app needs to function.

NO fake borrowers / lenders / DACA requests / email drafts / reviews etc.
All real data must come from the integrations (Jira, Typeform/Sheets, Gmail, Zendesk).

Usage: python -m scripts.seed_data
"""
import asyncio
import uuid
from datetime import datetime, timezone

from app.db.session import engine, AsyncSessionLocal, _is_sqlite
from app.db.base import Base
import app.models  # noqa: F401


async def seed():
    from sqlalchemy import select, func
    from app.models.oversight_config import OversightConfig

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Only structural default: a system-level oversight config with HUMAN_OVERSIGHT
        # so the state machine has a value to read on first run.
        result = await session.execute(
            select(func.count()).select_from(OversightConfig).where(OversightConfig.scope == "SYSTEM")
        )
        if (result.scalar() or 0) == 0:
            session.add(OversightConfig(
                id=uuid.uuid4(),
                scope="SYSTEM",
                stage=None,
                mode="HUMAN_OVERSIGHT",
                confidence_threshold=0.85,
                enabled=True,
                updated_by="system",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))
            await session.commit()
            print("Created default SYSTEM oversight config (HUMAN_OVERSIGHT, threshold 0.85)")
        else:
            print("SYSTEM oversight config already exists; skipping.")


if __name__ == "__main__":
    asyncio.run(seed())
