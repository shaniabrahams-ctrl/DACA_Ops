"""
Slack notifier — post DACA ops alerts to #daca-ops (and fraud-review pings to #csfraud).

The #daca-ops channel is the team's inbound feed. When the tool detects a net-new
DACA request (email intake, new Jira ticket, Typeform submission) it should post a
crisp alert here so nothing is missed — replacing the incumbent Gumloop poster.

Internal ops notification (not client-facing), so it posts on detection rather than
requiring per-message approval — but it is idempotent-by-caller (notify only on the
`created`/newly-flagged sets the syncs return) so it never re-spams the same request.
Dedup is the lesson from GUMLOOP_AGENT_REVIEW (duplicate alerts erode trust).

TWO SIGNAL STRENGTHS (no-infer rule):
  - CLEAN  (format_ping_a_clean)      — unambiguous net-new; informational, no buttons.
  - AMBIGUOUS (format_ping_a_ambiguous) — possible net-new; Yes/No buttons, tool waits.
Ping B (format_ping_b) fires on a Typeform application submission: a parallel
#csfraud fraud-review request (format_csfraud_request) plus a staged-not-created
Jira ticket the rep confirms.

SLACK INTERACTIVITY — HONEST LIMITATION: the buttons below are correctly-shaped
Block Kit `actions` elements (action_id + value), ready for a receiver. But there is
no Slack interactivity/Events endpoint in this app yet (that's R13, gated on the
Rhollout deploy — see NEXT_SESSION_HANDOFF.md). Clicking a button in real Slack will
not currently trigger anything server-side. The equivalent in-app confirm/dismiss
actions (see app.py's /intake/{thread_id}/confirm|dismiss and /case/{id}/create-ticket)
are the real, working path until that endpoint exists.

CREDENTIALS: `SLACK_BOT_TOKEN` (a bot token with chat:write) + `SLACK_CHANNEL`
(default the #daca-ops id) + `SLACK_CSFRAUD_CHANNEL` (default "#csfraud"). Never
committed. If unset, format_* still works (for preview/tests) and post_blocks()/post()
are no-ops that report "not configured" — so a deployment without Slack set simply
doesn't post, rather than crashing.
"""

from __future__ import annotations
import os

DEFAULT_CHANNEL = "C0APFKNF8SY"  # #daca-ops
DEFAULT_CSFRAUD_CHANNEL = "#csfraud"


def configured() -> bool:
    return bool(os.environ.get("SLACK_BOT_TOKEN"))


def _channel() -> str:
    return os.environ.get("SLACK_CHANNEL", DEFAULT_CHANNEL)


def _csfraud_channel() -> str:
    return os.environ.get("SLACK_CSFRAUD_CHANNEL", DEFAULT_CSFRAUD_CHANNEL)


def _case_link(case_id: str, app_base: str = "") -> str:
    return f"{app_base.rstrip('/')}/case/{case_id}" if app_base else f"/case/{case_id}"


def format_ping_a_clean(case_id: str, entity: str, requester_email: str, subject: str,
                        origin: str, received: str, app_base: str = "") -> dict:
    """Ping A, clean signal — informational only, no buttons. Lender is always shown
    as 'not provided yet' here: the case has just been opened from an email and the
    no-infer rule forbids guessing it."""
    link = _case_link(case_id, app_base)
    fields = [
        {"type": "mrkdwn", "text": f"*Business/entity:*\n{entity}"},
        {"type": "mrkdwn", "text": f"*Contact:*\n{requester_email or '—'}"},
        {"type": "mrkdwn", "text": f"*Origin:*\n{origin or '—'}"},
        {"type": "mrkdwn", "text": "*Lender:*\nnot provided yet"},
        {"type": "mrkdwn", "text": f"*Arrived:*\n{received or '—'}"},
    ]
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": ":new: *New DACA request*" + (f"\n*Re:* {subject}" if subject else "")}},
        {"type": "section", "fields": fields},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"Not yet in the tracker/Jira — needs triage. <{link}|Open in DACA Ops>"}]},
    ]
    return {"channel": _channel(), "text": f"New DACA request — {entity}", "blocks": blocks}


def format_ping_a_ambiguous(thread_id: str, candidate_entity: str, requester_email: str,
                            subject: str, reasons: list[str]) -> dict:
    """Ping A, ambiguous signal — no case opened, no net-new asserted. Yes/No buttons
    let a human make the call the tool won't guess at (no-infer rule)."""
    reasons_txt = "; ".join(reasons) or "signal unclear"
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": ":grey_question: *Possible new DACA request — confirm?*"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Possible client:*\n{candidate_entity}"},
            {"type": "mrkdwn", "text": f"*Contact:*\n{requester_email or '—'}"},
            {"type": "mrkdwn", "text": f"*Subject:*\n{subject or '(no subject)'}"},
        ]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Why flagged: {reasons_txt}"}]},
        {"type": "actions", "elements": [
            {"type": "button", "style": "primary", "action_id": "intake_confirm_new",
             "value": thread_id, "text": {"type": "plain_text", "text": "Yes — open case"}},
            {"type": "button", "action_id": "intake_dismiss_new", "value": thread_id,
             "text": {"type": "plain_text", "text": "No — existing / not a DACA request"}},
        ]},
    ]
    return {"channel": _channel(),
           "text": f"Possible new DACA request — confirm? ({candidate_entity})", "blocks": blocks}


def format_ping_b(case_id: str, entity: str, staged_summary: str, app_base: str = "") -> dict:
    """Ping B — DACA Application Form submitted. Actionable: a 'Confirm & create Jira
    ticket' button (idempotent regardless of clicks/where clicked). The #csfraud
    fraud-review request runs in parallel and never gates this."""
    link = _case_link(case_id, app_base)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f":page_facing_up: *DACA Application Form submitted* — {entity}"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"Fraud review requested in <#{_csfraud_channel().lstrip('#')}|{_csfraud_channel().lstrip('#')}> "
                 f"(runs in parallel, doesn't block). <{link}|Open case>"}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Staged Jira ticket:*\n{staged_summary}"}},
        {"type": "actions", "elements": [
            {"type": "button", "style": "primary", "action_id": "confirm_create_jira",
             "value": case_id, "text": {"type": "plain_text", "text": "Confirm & create Jira ticket"}},
        ]},
    ]
    return {"channel": _channel(), "text": f"DACA Application Form submitted — {entity}", "blocks": blocks}


def format_csfraud_request(case_id: str, entity: str, app_base: str = "") -> dict:
    """Fraud-review request posted to #csfraud in parallel with Ping B. Informational —
    the fraud team reviews on their own Jira workflow; this never gates the ticket
    confirm step."""
    link = _case_link(case_id, app_base)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
         "text": f":rotating_light: *Fraud review requested* — {entity}"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"DACA Application Form submitted. <{link}|Open in DACA Ops>"}]},
    ]
    return {"channel": _csfraud_channel(), "text": f"Fraud review requested — {entity}", "blocks": blocks}


def post_blocks(payload: dict) -> dict:
    """Post a composed Block Kit payload ({channel, text, blocks}). Never raises on a
    config gap — returns {"ok": False, "reason": ...} so a missing SLACK_BOT_TOKEN
    degrades to 'didn't post' rather than a crash."""
    if not configured():
        return {"ok": False, "reason": "SLACK_BOT_TOKEN not set"}
    import httpx
    resp = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
        json={**payload, "unfurl_links": False},
        timeout=30,
    )
    return resp.json()


def post(text: str, channel: str | None = None) -> dict:
    """Post a plain-text message. Kept for simple internal notes; prefer post_blocks()
    for the formatted pings above. Never raises on a config gap."""
    if not configured():
        return {"ok": False, "reason": "SLACK_BOT_TOKEN not set"}
    import httpx
    resp = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
        json={"channel": channel or _channel(), "text": text, "unfurl_links": False},
        timeout=30,
    )
    return resp.json()
