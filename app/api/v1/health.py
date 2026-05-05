"""
Health check endpoint — verifies database and Redis connectivity.
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
import redis.asyncio as aioredis

from app.dependencies import SessionDep
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check(db: SessionDep):
    """Returns service health status including DB and Redis connectivity."""
    checks: dict[str, str] = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # Redis check
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = all(v == "ok" for v in checks.values())
    status = "ok" if all_ok else "degraded"

    if checks.get("database") != "ok":
        raise HTTPException(status_code=503, detail={"status": status, "checks": checks})

    return {"status": status, "checks": checks, "version": "1.0.0"}
