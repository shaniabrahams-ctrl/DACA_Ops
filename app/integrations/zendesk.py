"""
Zendesk Integration — create and manage support tickets.

Used for escalations and borrower/lender support queries
related to DACA processing.

Auth: API token (ZENDESK_API_TOKEN + ZENDESK_EMAIL)
"""
import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


def _auth() -> tuple[str, str]:
    return (f"{settings.zendesk_email}/token", settings.zendesk_api_token)


def _base_url() -> str:
    return f"{settings.zendesk_subdomain}/api/v2"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def create_ticket(
    subject: str,
    description: str,
    requester_email: str | None = None,
    requester_name: str | None = None,
    priority: str = "normal",
    tags: list[str] | None = None,
    custom_fields: list[dict[str, Any]] | None = None,
    external_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a Zendesk ticket.
    external_id can be set to the DacaRequest.external_ref for cross-referencing.
    """
    ticket: dict[str, Any] = {
        "subject": subject,
        "comment": {"body": description},
        "priority": priority,
    }
    if requester_email:
        ticket["requester"] = {"email": requester_email}
        if requester_name:
            ticket["requester"]["name"] = requester_name
    if tags:
        ticket["tags"] = tags
    if custom_fields:
        ticket["custom_fields"] = custom_fields
    if external_id:
        ticket["external_id"] = external_id

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{_base_url()}/tickets.json",
            auth=_auth(),
            json={"ticket": ticket},
        )
        response.raise_for_status()
        return response.json()["ticket"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def update_ticket(
    ticket_id: int,
    *,
    status: str | None = None,
    priority: str | None = None,
    comment: str | None = None,
    tags: list[str] | None = None,
    internal_note: str | None = None,
) -> dict[str, Any]:
    """Update an existing Zendesk ticket."""
    ticket: dict[str, Any] = {}
    if status:
        ticket["status"] = status
    if priority:
        ticket["priority"] = priority
    if tags:
        ticket["tags"] = tags
    if comment:
        ticket["comment"] = {"body": comment, "public": True}
    elif internal_note:
        ticket["comment"] = {"body": internal_note, "public": False}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.put(
            f"{_base_url()}/tickets/{ticket_id}.json",
            auth=_auth(),
            json={"ticket": ticket},
        )
        response.raise_for_status()
        return response.json()["ticket"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Fetch a Zendesk ticket by ID."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{_base_url()}/tickets/{ticket_id}.json",
            auth=_auth(),
        )
        response.raise_for_status()
        return response.json()["ticket"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def search_tickets(
    query: str,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> list[dict[str, Any]]:
    """
    Search Zendesk tickets using their search API.
    e.g. query='type:ticket external_id:DACA-2026-0042'
    """
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{_base_url()}/search.json",
            auth=_auth(),
            params={
                "query": query,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )
        response.raise_for_status()
        return response.json().get("results", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def add_comment(
    ticket_id: int,
    body: str,
    public: bool = True,
) -> dict[str, Any]:
    """Add a comment (public reply or internal note) to a ticket."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.put(
            f"{_base_url()}/tickets/{ticket_id}.json",
            auth=_auth(),
            json={
                "ticket": {
                    "comment": {"body": body, "public": public},
                }
            },
        )
        response.raise_for_status()
        return response.json()["ticket"]


async def find_ticket_by_daca_ref(external_ref: str) -> dict[str, Any] | None:
    """Look up a Zendesk ticket by DACA external_ref (stored as external_id)."""
    results = await search_tickets(f"type:ticket external_id:{external_ref}")
    return results[0] if results else None
