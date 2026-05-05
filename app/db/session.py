from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    from sqlalchemy.ext.compiler import compiles
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

    @compiles(JSONB, "sqlite")
    def _jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    @compiles(PG_UUID, "sqlite")
    def _uuid_sqlite(type_, compiler, **kw):
        return "CHAR(32)"

_engine_kwargs: dict = {
    "echo": settings.app_env == "development",
}
if not _is_sqlite:
    _engine_kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
