"""
FastAPI application factory for DACA Operations Platform.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.router import api_router

logger = logging.getLogger(__name__)


async def _initial_sync():
    """Run all integration syncs on startup. Failures are logged, not fatal."""
    from app.services.jira_sync_service import sync_from_jira
    from app.services.typeform_sync_service import sync_typeform_submissions
    from app.services.gmail_sync_service import poll_and_sync_emails
    from app.services.zendesk_sync_service import sync_zendesk_tickets

    for name, fn in [
        ("Jira", sync_from_jira),
        ("Typeform/Sheets", sync_typeform_submissions),
        ("Gmail", poll_and_sync_emails),
        ("Zendesk", sync_zendesk_tickets),
    ]:
        try:
            logger.info("Running initial %s sync...", name)
            result = await fn()
            logger.info("Initial %s sync complete: %s", name, result)
        except Exception:
            logger.exception("Initial %s sync failed (non-fatal)", name)


async def _polling_loop():
    """Background loop that periodically syncs data from external systems."""
    from app.services.jira_sync_service import sync_from_jira
    from app.services.typeform_sync_service import sync_typeform_submissions
    from app.services.gmail_sync_service import poll_and_sync_emails
    from app.services.zendesk_sync_service import sync_zendesk_tickets

    gmail_interval = settings.gmail_poll_interval_seconds
    typeform_interval = settings.typeform_poll_interval_minutes * 60
    jira_interval = 5 * 60
    zendesk_interval = 3 * 60

    gmail_counter = 0
    typeform_counter = 0
    jira_counter = 0
    zendesk_counter = 0
    tick = 30

    while True:
        await asyncio.sleep(tick)
        gmail_counter += tick
        typeform_counter += tick
        jira_counter += tick
        zendesk_counter += tick

        if gmail_counter >= gmail_interval:
            gmail_counter = 0
            try:
                await poll_and_sync_emails()
            except Exception:
                logger.exception("Gmail polling error")

        if typeform_counter >= typeform_interval:
            typeform_counter = 0
            try:
                await sync_typeform_submissions()
            except Exception:
                logger.exception("Typeform polling error")

        if jira_counter >= jira_interval:
            jira_counter = 0
            try:
                await sync_from_jira()
            except Exception:
                logger.exception("Jira polling error")

        if zendesk_counter >= zendesk_interval:
            zendesk_counter = 0
            try:
                await sync_zendesk_tickets()
            except Exception:
                logger.exception("Zendesk polling error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import engine, _is_sqlite
    if _is_sqlite:
        from app.db.base import Base
        import app.models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    await _initial_sync()
    poll_task = asyncio.create_task(_polling_loop())
    yield
    poll_task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DACA Operations Platform",
        description=(
            "Internal platform for managing Deposit Account Control Agreements "
            "between Rho, Webster Bank, Borrowers, and Lenders."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS — allow the React frontend and local dev
    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    if settings.app_env == "production":
        origins = ["https://daca-ops.rho.co"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
