"""
Slack Integration — sends messages and Block Kit notifications.

Bot token: stored in SLACK_BOT_TOKEN env var.
Primary channel: #daca-ops (C0APFKNF8SY)
"""
import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.slack_bot_token}",
        "Content-Type": "application/json",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def send_message(channel_id: str, text: str) -> dict[str, Any]:
    """Send a plain-text message to a Slack channel."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers=_headers(),
            json={"channel": channel_id, "text": text},
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error')}")
        return data


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def send_blocks(channel_id: str, blocks: list[dict[str, Any]], text: str = "") -> dict[str, Any]:
    """Send a Block Kit message to a Slack channel."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{SLACK_API_BASE}/chat.postMessage",
            headers=_headers(),
            json={"channel": channel_id, "blocks": blocks, "text": text},
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error')}")
        return data


async def send_weekly_update(
    channel_id: str,
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Sends the Tuesday 10AM ET weekly DACA status update in traffic-light format.
    Each update: {external_ref, lender, borrower, status, emoji, note}
    """
    from datetime import date
    today = date.today().strftime("%B %d, %Y")

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"DACA Weekly Update — {today}"},
        },
        {"type": "divider"},
    ]

    for item in updates:
        emoji = item.get("emoji", ":white_circle:")
        ref = item.get("external_ref", "")
        lender = item.get("lender", "")
        borrower = item.get("borrower", "")
        status = item.get("status", "")
        note = item.get("note", "")

        text = f"{emoji} *{ref}* — {borrower} / {lender}\nStatus: *{status}*"
        if note:
            text += f"\n_{note}_"

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    return await send_blocks(channel_id=channel_id, blocks=blocks, text=f"DACA Weekly Update — {today}")
