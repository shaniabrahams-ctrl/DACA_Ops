"""
Jira Integration — create and update tickets on the CS board.

Project: CS (https://rho.atlassian.net)
Auth: API token (JIRA_API_TOKEN + JIRA_USER_EMAIL)
"""
import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


def _auth() -> tuple[str, str]:
    return (settings.jira_user_email, settings.jira_api_token)


def _base_url() -> str:
    return f"{settings.jira_base_url}/rest/api/3"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def create_issue(
    summary: str,
    description: str,
    issue_type: str = "Task",
    priority: str = "Medium",
    labels: list[str] | None = None,
    assignee_account_id: str | None = None,
) -> dict[str, Any]:
    """Create a Jira issue in the CS project."""
    payload: dict[str, Any] = {
        "fields": {
            "project": {"key": settings.jira_project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                ],
            },
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
    }
    if labels:
        payload["fields"]["labels"] = labels
    if assignee_account_id:
        payload["fields"]["assignee"] = {"accountId": assignee_account_id}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{_base_url()}/issue",
            auth=_auth(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def transition_issue(issue_key: str, status: str) -> None:
    """Transition a Jira issue to the given status name."""
    # First, get available transitions
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{_base_url()}/issue/{issue_key}/transitions",
            auth=_auth(),
        )
        resp.raise_for_status()
        transitions = resp.json().get("transitions", [])

        transition_id = next(
            (t["id"] for t in transitions if t["name"].lower() == status.lower()),
            None,
        )
        if transition_id is None:
            logger.warning("No Jira transition found for status '%s' on %s", status, issue_key)
            return

        await client.post(
            f"{_base_url()}/issue/{issue_key}/transitions",
            auth=_auth(),
            json={"transition": {"id": transition_id}},
        )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def add_comment(issue_key: str, comment: str) -> None:
    """Add a comment to a Jira issue."""
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": comment}]}
            ],
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{_base_url()}/issue/{issue_key}/comment",
            auth=_auth(),
            json=payload,
        )
        resp.raise_for_status()
