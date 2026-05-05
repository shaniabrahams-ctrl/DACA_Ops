"""
Test configuration and shared fixtures.
"""
import asyncio
import pytest
import pytest_asyncio
from sqlalchemy import event as sa_event, JSON, String
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.db.base import Base

# Use an in-memory SQLite database for tests (asyncio mode)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ---------- SQLite type compatibility shims for PostgreSQL-specific types ----------
# SQLite has no JSONB or native UUID type. We compile them to JSON / CHAR(32) so that
# ``Base.metadata.create_all`` works against the test SQLite engine.

from sqlalchemy.ext.compiler import compiles

@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

@compiles(PG_UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(32)"


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
