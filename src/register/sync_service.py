"""
Sync service (R12) — refresh the register from live sources, in-app or on a schedule.

This is the step that lets the tool run without an agent feeding it snapshots: it
pulls Jira + Salesforce + the DACA Summary sheet itself (via the clients in
src/register/clients), runs the existing idempotent sync_* functions, and writes a
`sync_runs` receipt. Locally it's a `/sync` button / CLI; on Rhollout a scheduled
job calls run_sync() with service credentials.

RESILIENCE: sources are synced independently — a Jira outage doesn't block the sheet
sync. Each source's outcome (counts or error) is captured, and one combined receipt
plus per-source receipts are written. The sync_* functions are idempotent, so a
re-run produces no duplicate events.

CREDENTIALS: build_sources_from_env() reads env (.env locally, Secret Manager on
Rhollout). A source with missing creds is reported as "not configured" rather than
crashing the whole run — so the app stays usable locally with only some sources set.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional

from src.register.db import Register
from src.register.sync_gsheet import sync_gsheet
from src.register.sync_jira import sync_all as sync_jira_all
from src.register.sync_salesforce import sync_salesforce
from src.register.intake_email import sync_email_intake
from src.integrations import slack_notify


@dataclass
class Sources:
    gsheet: Optional[object] = None
    jira: Optional[object] = None
    salesforce: Optional[object] = None
    gmail: Optional[object] = None


def build_sources_from_env() -> Sources:
    """Construct the real clients from environment configuration."""
    from src.register.clients.jira_client import JiraClient
    from src.register.clients.salesforce_client import SalesforceClient
    from src.register.clients.gsheet_client import GSheetClient
    from src.register.clients.gmail_client import GmailClient
    return Sources(gsheet=GSheetClient(), jira=JiraClient(),
                   salesforce=SalesforceClient(), gmail=GmailClient())


def _notify_new(reg: Register, case_ids: list[str], source: str) -> int:
    """Post a #daca-ops Ping A (clean) for each newly-created case. Automatic (internal
    ops notification, not client-facing) — no per-message gate; only fires on the
    freshly created set so it never re-spams. No-op when Slack isn't configured."""
    posted = 0
    for cid in case_ids:
        c = reg.get_case(cid)
        if not c:
            continue
        contact = next((p.get("email") for p in reg.parties_for(cid)
                        if p.get("role") == "borrower_contact" and p.get("email")), "")
        payload = slack_notify.format_ping_a_clean(
            case_id=cid, entity=c.entity_legal_name, requester_email=contact, subject="",
            origin=source, received=c.initial_inquiry_date or "")
        res = slack_notify.post_blocks(payload)
        if res.get("ok"):
            posted += 1
    return posted


def _notify_ambiguous(signals: list[dict]) -> int:
    """Post a #daca-ops Ping A (ambiguous) confirm-ping for each newly-flagged signal.
    No case exists for these — see intake_email.classify. No-op when Slack isn't
    configured."""
    posted = 0
    for s in signals:
        payload = slack_notify.format_ping_a_ambiguous(
            thread_id=s.get("thread_id", ""), candidate_entity=s["candidate_entity"],
            requester_email=s.get("requester_email", ""), subject=s.get("subject", ""),
            reasons=s["reasons"])
        res = slack_notify.post_blocks(payload)
        if res.get("ok"):
            posted += 1
    return posted


def _record(reg: Register, ts: str, source: str, ok: bool, detail) -> None:
    reg.conn.execute(
        "INSERT INTO sync_runs (ts, source, ok, detail) VALUES (?,?,?,?)",
        (ts, source, 1 if ok else 0, json.dumps(detail)))
    reg.conn.commit()


def _configured(client) -> bool:
    # clients expose configured(); treat a missing client as not configured
    return bool(client and getattr(client, "configured", lambda: True)())


def run_sync(reg: Register, sources: Sources, now_iso: str) -> dict:
    """
    Fetch each configured source and apply its sync. Returns a report dict:
      {"ok": bool, "sources": {name: {status, ...counts | error}}}
    Order mirrors the seed: gsheet (backbone) -> jira (pipeline) -> salesforce (status).
    """
    report: dict = {"ran_at": now_iso, "sources": {}}

    # 1) DACA Summary sheet — the Business-ID backbone
    if _configured(sources.gsheet):
        try:
            content = sources.gsheet.fetch()
            rep = sync_gsheet(reg, content, now_iso)
            report["sources"]["gsheet"] = {"status": "ok", **rep}
            _record(reg, now_iso, "gsheet", True, rep)
        except Exception as e:
            report["sources"]["gsheet"] = {"status": "error", "error": str(e)}
            _record(reg, now_iso, "gsheet", False, {"error": str(e)})
    else:
        report["sources"]["gsheet"] = {"status": "not_configured"}

    # 2) Jira — live pipeline stage
    if _configured(sources.jira):
        try:
            tickets = sources.jira.fetch()
            rep = sync_jira_all(reg, tickets, now_iso)
            rep.pop("per_case", None)
            report["sources"]["jira"] = {"status": "ok", **rep}
            _record(reg, now_iso, "jira", True, rep)
        except Exception as e:
            report["sources"]["jira"] = {"status": "error", "error": str(e)}
            _record(reg, now_iso, "jira", False, {"error": str(e)})
    else:
        report["sources"]["jira"] = {"status": "not_configured"}

    # 3) Salesforce — authoritative status/type overlay
    if _configured(sources.salesforce):
        try:
            records = sources.salesforce.fetch()
            rep = sync_salesforce(reg, records, now_iso)
            report["sources"]["salesforce"] = {"status": "ok", **rep}
            _record(reg, now_iso, "salesforce", True, rep)
        except Exception as e:
            report["sources"]["salesforce"] = {"status": "error", "error": str(e)}
            _record(reg, now_iso, "salesforce", False, {"error": str(e)})
    else:
        report["sources"]["salesforce"] = {"status": "not_configured"}

    # 4) Gmail — net-new DACA inquiries that arrived only by email. New cases are
    #    posted to #daca-ops automatically (the tool's own new-request notifier).
    if _configured(sources.gmail):
        try:
            threads = sources.gmail.fetch()
            rep = sync_email_intake(reg, threads, now_iso)
            notified = _notify_new(reg, rep["created"], source="email")
            report["sources"]["gmail"] = {"status": "ok", "new": len(rep["created"]),
                                          "seen": rep["seen"], "notified": notified}
            _record(reg, now_iso, "gmail", True, {**rep, "notified": notified})
        except Exception as e:
            report["sources"]["gmail"] = {"status": "error", "error": str(e)}
            _record(reg, now_iso, "gmail", False, {"error": str(e)})
    else:
        report["sources"]["gmail"] = {"status": "not_configured"}

    statuses = [s["status"] for s in report["sources"].values()]
    report["ok"] = "error" not in statuses
    report["total_cases"] = len(reg.all_cases())
    report["any_configured"] = any(s != "not_configured" for s in statuses)
    _record(reg, now_iso, "all", report["ok"], {k: v.get("status") for k, v in report["sources"].items()})
    return report


def last_sync_runs(reg: Register, limit: int = 10) -> list[dict]:
    cur = reg.conn.execute(
        "SELECT ts, source, ok, detail FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,))
    return [{"ts": r[0], "source": r[1], "ok": bool(r[2]),
             "detail": json.loads(r[3] or "null")} for r in cur.fetchall()]
