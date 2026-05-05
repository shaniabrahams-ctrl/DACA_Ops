"""
Sync API — trigger manual data syncs from Jira, Google Sheets, and Gmail.
Also reports integration connection status.
"""
import logging
from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status")
async def integration_status():
    """Show which integrations are configured and ready."""
    return {
        "jira": {
            "configured": bool(settings.jira_api_token),
            "base_url": settings.jira_base_url,
            "project_key": settings.jira_project_key,
        },
        "google": {
            "configured": bool(settings.google_service_account_json)
            and not settings.google_service_account_json.startswith("/"),
            "gmail_user": settings.gmail_delegated_user,
            "typeform_sheet_id": settings.typeform_sheet_id,
        },
        "slack": {
            "configured": bool(settings.slack_bot_token)
            and settings.slack_bot_token != "xoxb-",
            "primary_channel": settings.slack_daca_ops_channel_id,
        },
        "zendesk": {
            "configured": bool(settings.zendesk_api_token),
            "subdomain": settings.zendesk_subdomain,
        },
    }


@router.post("/jira")
async def sync_jira():
    """Manually trigger a Jira sync."""
    from app.services.jira_sync_service import sync_from_jira
    result = await sync_from_jira()
    return {"source": "jira", "result": result}


@router.post("/typeform")
async def sync_typeform():
    """Manually trigger a Typeform/Google Sheets sync."""
    from app.services.typeform_sync_service import sync_typeform_submissions
    count = await sync_typeform_submissions()
    return {"source": "typeform", "result": {"processed": count}}


@router.post("/gmail")
async def sync_gmail():
    """Manually trigger a Gmail sync."""
    from app.services.gmail_sync_service import poll_and_sync_emails
    await poll_and_sync_emails()
    return {"source": "gmail", "result": "complete"}


@router.post("/all")
async def sync_all():
    """Trigger all syncs sequentially."""
    from app.services.jira_sync_service import sync_from_jira
    from app.services.typeform_sync_service import sync_typeform_submissions
    from app.services.gmail_sync_service import poll_and_sync_emails

    results = {}
    for name, fn in [("jira", sync_from_jira), ("typeform", sync_typeform_submissions), ("gmail", poll_and_sync_emails)]:
        try:
            r = await fn()
            results[name] = {"status": "ok", "result": r}
        except Exception as e:
            logger.exception("Manual %s sync failed", name)
            results[name] = {"status": "error", "error": str(e)}

    return results
