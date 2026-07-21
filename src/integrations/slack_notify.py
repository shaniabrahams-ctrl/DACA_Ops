"""
Slack notifier — post DACA ops alerts (new requests, etc.) to #daca-ops.

The #daca-ops channel is the team's inbound feed. When the tool detects a net-new
DACA request (email intake, new Jira ticket, Typeform submission) it should post a
crisp alert here so nothing is missed — replacing the incumbent Gumloop poster.

Internal ops notification (not client-facing), so it posts on detection rather than
requiring per-message approval — but it is idempotent-by-caller (notify only on the
`created` set the syncs return) so it never re-spams the same request. Dedup is the
lesson from GUMLOOP_AGENT_REVIEW (duplicate alerts erode trust in the channel).

CREDENTIALS: `SLACK_BOT_TOKEN` (a bot token with chat:write) + `SLACK_CHANNEL`
(default the #daca-ops id). Never committed. If unset, format_* still works (for
preview/tests) and post() is a no-op that reports "not configured" — so a deployment
without Slack set simply doesn't post, rather than crashing.
"""

from __future__ import annotations
import os

DEFAULT_CHANNEL = "C0APFKNF8SY"  # #daca-ops


def configured() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN"))


def format_new_request(entity: str, requester: str, subject: str,
                       received: str, case_id: str, source: str = "email",
                       app_base: str = "") -> str:
    """Compose the new-request alert text (Slack mrkdwn)."""
    link = f"{app_base.rstrip('/')}/case/{case_id}" if app_base else f"/case/{case_id}"
    lines = [
        ":new: *New DACA request*" + (f"  ·  _{source}_" if source else ""),
        f"*Client:* {entity}" + (f"  ·  {requester}" if requester else ""),
    ]
    if subject:
        lines.append(f"*Re:* {subject}")
    if received:
        lines.append(f"*Received:* {received}")
    lines.append(f"Not yet in the tracker/Jira — needs triage. Open in DACA Ops: {link}")
    return "\n".join(lines)


def post(text: str, channel: str | None = None) -> dict:
    """Post to Slack via the Web API. Returns {ok, ...}; never raises on a config gap."""
    if not configured():
        return {"ok": False, "reason": "SLACK_BOT_TOKEN not set"}
    import httpx
    channel = channel or os.environ.get("SLACK_CHANNEL", DEFAULT_CHANNEL)
    resp = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
        json={"channel": channel, "text": text, "unfurl_links": False},
        timeout=30,
    )
    return resp.json()
