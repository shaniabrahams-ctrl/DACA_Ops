"""
Jira Sync Service — pull existing tickets from the CS Jira board and
create/update DacaRequest records in the database.

Called on startup and periodically to keep local state in sync with Jira.
"""
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, func

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.integrations.jira import transition_issue, _auth, _base_url
from app.models.daca_request import DacaRequest, DacaRequestStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Priority mapping: Jira priority name -> DACA priority
# ---------------------------------------------------------------------------
_JIRA_PRIORITY_MAP: dict[str, str] = {
    "Highest": "URGENT",
    "High": "HIGH",
    "Medium": "NORMAL",
    "Low": "NORMAL",
    "Lowest": "NORMAL",
}


def _map_priority(jira_priority: str | None) -> str:
    """Convert a Jira priority name to a DACA priority string."""
    if jira_priority is None:
        return "NORMAL"
    return _JIRA_PRIORITY_MAP.get(jira_priority, "NORMAL")


def _extract_plain_text(adf_body: dict | None) -> str:
    """Best-effort extraction of plain text from Jira ADF description."""
    if not adf_body:
        return ""
    parts: list[str] = []

    def _walk(node: dict) -> None:
        if node.get("type") == "text":
            parts.append(node.get("text", ""))
        for child in node.get("content", []):
            if isinstance(child, dict):
                _walk(child)

    _walk(adf_body)
    return " ".join(parts).strip()


def _next_external_ref(year: int, sequence: int) -> str:
    return f"DACA-{year}-{sequence:04d}"


# ---------------------------------------------------------------------------
# 1. Search Jira for all issues in the CS project
# ---------------------------------------------------------------------------
async def search_jira_issues() -> list[dict[str, Any]]:
    """Search the CS project for all DACA-related issues using JQL.

    Pages through results automatically and returns the full raw issue list.
    """
    if not settings.jira_api_token:
        logger.info("Jira API token not configured; skipping Jira search.")
        return []

    jql = f"project = {settings.jira_project_key} ORDER BY created DESC"
    all_issues: list[dict[str, Any]] = []
    start_at = 0
    max_results = 100

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": "summary,description,status,priority,assignee,created,updated",
            }
            resp = await client.get(
                f"{_base_url()}/search",
                auth=_auth(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            issues = data.get("issues", [])
            all_issues.extend(issues)

            # Check if there are more pages
            total = data.get("total", 0)
            start_at += len(issues)
            if start_at >= total or not issues:
                break

    logger.info("Fetched %d issues from Jira project %s.", len(all_issues), settings.jira_project_key)
    return all_issues


# ---------------------------------------------------------------------------
# 2. Main sync: Jira -> local DB
# ---------------------------------------------------------------------------
async def sync_from_jira() -> dict[str, int]:
    """Pull all CS project issues from Jira and create/update DacaRequest records.

    Returns a summary dict with counts: {"created": N, "updated": N, "unchanged": N}.
    """
    if not settings.jira_api_token:
        logger.info("Jira API token not configured; skipping Jira sync.")
        return {"created": 0, "updated": 0, "unchanged": 0}

    issues = await search_jira_issues()
    if not issues:
        logger.info("No issues returned from Jira; nothing to sync.")
        return {"created": 0, "updated": 0, "unchanged": 0}

    created = 0
    updated = 0
    unchanged = 0

    async with AsyncSessionLocal() as session:
        # Pre-fetch all existing jira_ticket_keys so we can detect new vs existing
        result = await session.execute(
            select(DacaRequest.jira_ticket_key, DacaRequest.id, DacaRequest.jira_status)
            .where(DacaRequest.jira_ticket_key.isnot(None))
        )
        existing_map: dict[str, tuple[Any, str | None]] = {
            row.jira_ticket_key: (row.id, row.jira_status)
            for row in result.all()
        }

        # Determine next external_ref sequence number
        year = datetime.now(timezone.utc).year
        count_result = await session.execute(
            select(func.count(DacaRequest.id)).where(
                DacaRequest.external_ref.like(f"DACA-{year}-%")
            )
        )
        sequence = (count_result.scalar() or 0) + 1

        for issue in issues:
            ticket_key = issue.get("key", "")
            fields = issue.get("fields", {})

            jira_status_name = (fields.get("status") or {}).get("name", "")
            jira_priority_name = (fields.get("priority") or {}).get("name", "")
            summary = fields.get("summary", "")
            description_adf = fields.get("description")
            description_text = _extract_plain_text(description_adf)
            assignee_display = None
            if fields.get("assignee"):
                assignee_display = fields["assignee"].get("displayName") or fields["assignee"].get("emailAddress")

            if ticket_key in existing_map:
                # -- Update path: only touch jira_status if it changed --
                req_id, current_jira_status = existing_map[ticket_key]
                if current_jira_status != jira_status_name:
                    await session.execute(
                        select(DacaRequest).where(DacaRequest.id == req_id)
                    )
                    req = await session.get(DacaRequest, req_id)
                    if req is not None:
                        req.jira_status = jira_status_name
                        # If the Jira status is a known DACA status, sync it
                        if jira_status_name in DacaRequestStatus.ALL_STATUSES:
                            req.previous_status = req.status
                            req.status = jira_status_name
                        logger.info(
                            "Updated %s jira_status: %s -> %s",
                            ticket_key,
                            current_jira_status,
                            jira_status_name,
                        )
                    updated += 1
                else:
                    unchanged += 1
            else:
                # -- Create path: new DacaRequest record --
                external_ref = _next_external_ref(year, sequence)
                sequence += 1

                # Map Jira status to DacaRequest status if it is a recognized status
                initial_status = (
                    jira_status_name
                    if jira_status_name in DacaRequestStatus.ALL_STATUSES
                    else DacaRequestStatus.FRAUD_INITIAL_REVIEW
                )

                new_request = DacaRequest(
                    external_ref=external_ref,
                    status=initial_status,
                    jira_ticket_key=ticket_key,
                    jira_status=jira_status_name,
                    priority=_map_priority(jira_priority_name),
                    source_channel="JIRA",
                    assigned_to=assignee_display,
                    metadata_={
                        "jira_summary": summary,
                        "jira_description": description_text[:2000] if description_text else "",
                    },
                )
                session.add(new_request)
                logger.info(
                    "Created DacaRequest %s from Jira ticket %s (status=%s, priority=%s).",
                    external_ref,
                    ticket_key,
                    initial_status,
                    new_request.priority,
                )
                created += 1

        await session.commit()

    summary_counts = {"created": created, "updated": updated, "unchanged": unchanged}
    logger.info("Jira sync complete: %s", summary_counts)
    return summary_counts


# ---------------------------------------------------------------------------
# 3. Push status change from our system -> Jira
# ---------------------------------------------------------------------------
async def sync_status_to_jira(jira_ticket_key: str, new_status: str) -> None:
    """When a DacaRequest status changes locally, push the update to Jira.

    Uses the existing ``transition_issue`` helper which resolves the
    transition ID by matching on the status name.
    """
    if not settings.jira_api_token:
        logger.info("Jira API token not configured; skipping status push for %s.", jira_ticket_key)
        return

    if not jira_ticket_key:
        logger.warning("sync_status_to_jira called with empty jira_ticket_key; skipping.")
        return

    logger.info("Pushing status '%s' to Jira ticket %s.", new_status, jira_ticket_key)
    try:
        await transition_issue(jira_ticket_key, new_status)
        logger.info("Successfully transitioned %s to '%s' in Jira.", jira_ticket_key, new_status)
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Failed to transition %s to '%s': HTTP %d — %s",
            jira_ticket_key,
            new_status,
            exc.response.status_code,
            exc.response.text[:500],
        )
    except Exception:
        logger.exception("Unexpected error transitioning %s to '%s' in Jira.", jira_ticket_key, new_status)
