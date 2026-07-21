"""
DACA Ops — local web application.

The clickable app. Same code that deploys to Rhollout; locally it runs against a
SQLite register seeded from real Jira + Salesforce data. Server-rendered HTML
(FastAPI + Jinja2), no JS framework, so it launches with one command and has no
build step.

Screens:
  /                     dashboard — KPIs, pipeline funnel, in-flight work queue,
                        needs-attention, active book
  /case/{case_id}       case detail — stage tracker, timeline, parties, stage actions
  /reports/webster      monthly Rho<>Webster report (R7)
  /sync                 live refresh from Jira/Salesforce/DACA Summary sheet (R12)
  POST /case/{id}/advance   move a case to a new lifecycle stage (event-logged)
  POST /case/{id}/note      append a human note (event-logged)

Net-new requests are NOT created by hand here — they arrive via daca@rho.co / Typeform
and land in the register through sync (R12) / the loan-agreement intake.

DATA: reads DACA_REGISTER_DB (env) — a real register. Live re-sync from Jira/SF
runs through src/register/sync_*.py, which on Rhollout is driven by a scheduled
job with service credentials; locally it's seeded from the real snapshot the
agent synced this session. Nothing here is fixture data.

HUMAN GATES: this app tracks and drafts. It never sends DocuSign, emails a client,
or writes back to Jira/Salesforce without an explicit action the operator takes —
consistent with the repo-wide approval rule.
"""

from __future__ import annotations
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import tempfile

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from src.register.db import Register, Case
from src.register.lifecycle import (
    LifecycleStage, ControlState, is_allowed_transition,
)
from src.register.pipeline import STAGE_ORDER, OFF_PIPELINE, STALE_DAYS, _days_since
from src.reports import webster_monthly as wm
from src.register.sync_service import run_sync, build_sources_from_env, last_sync_runs
from src.webapp.humanize import humanize_flag, SEV_ORDER

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get(
    "DACA_REGISTER_DB",
    str(BASE_DIR.parent.parent / "daca_register.db"),
)

app = FastAPI(title="DACA Ops")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Deep-link ticket keys (CSHELP-123, LEGALHELP-45, …) to Jira. Returns None for
# non-ticket identifiers (e.g. a numeric Business ID), so the template renders plain text.
JIRA_BROWSE = "https://rho.atlassian.net/browse/"
_JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def jira_url(key: str | None) -> str | None:
    return JIRA_BROWSE + key if key and _JIRA_KEY_RE.match(key) else None


templates.env.globals["jira_url"] = jira_url


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reg() -> Register:
    # one connection per request keeps SQLite happy across threads
    return Register(DB_PATH)


# operator identity — on Rhollout this comes from the gateway-authenticated user;
# locally it's set once so every event is still attributed to a real person.
OPERATOR = os.environ.get("DACA_OPERATOR", "human:shani.abrahams@rho.co")

STAGE_LABELS = {s.value: label for s, label in STAGE_ORDER}
STAGE_LABELS.update({s.value: label for s, label in OFF_PIPELINE})
ALL_STAGES = [(s.value, label) for s, label in STAGE_ORDER] + \
             [(s.value, label) for s, label in OFF_PIPELINE]


INFLIGHT_STAGES = [(s, label) for s, label in STAGE_ORDER if s != LifecycleStage.ACTIVE]


def _aging(days: int | None) -> str:
    if days is None:
        return "none"
    if days > STALE_DAYS:
        return "red"
    if days > 14:
        return "amber"
    return "ok"


def stage_progress(stage_value: str) -> dict | None:
    """End-to-end progress of a case along the canonical pipeline (…→ Active):
    a done/current/todo segment per stage, the current + next stage labels, and how
    many steps remain to Active. None for off-pipeline stages."""
    vals = [s.value for s, _ in STAGE_ORDER]
    if stage_value not in vals:
        return None
    idx = vals.index(stage_value)
    last = len(vals) - 1
    segs = [{"label": label,
             "status": "done" if i < idx else ("current" if i == idx else "todo")}
            for i, (s, label) in enumerate(STAGE_ORDER)]
    return {"segs": segs, "now": STAGE_ORDER[idx][1],
            "next": STAGE_ORDER[idx + 1][1] if idx < last else None,
            "remaining": last - idx, "step": idx + 1, "total": last + 1}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    r = reg()
    now = datetime.now(timezone.utc)
    cases = r.all_cases()
    by_stage = {}
    for c in cases:
        by_stage.setdefault(c.lifecycle_stage, []).append(c)

    def card(c):
        d = _days_since(c.stage_entered_at, now)
        return {"case": c, "days": d, "stale": d is not None and d > STALE_DAYS,
                "aging": _aging(d)}

    # In-flight cases as end-to-end progress rows (most-aged first).
    inflight_cards = []
    for s, label in INFLIGHT_STAGES:
        for c in by_stage.get(s.value, []):
            cd = card(c)
            cd["progress"] = stage_progress(c.lifecycle_stage)
            inflight_cards.append(cd)
    inflight_cards.sort(key=lambda cd: -(cd["days"] or 0))

    # Active book — compact, collapsed (progressive disclosure).
    active_cases = sorted(by_stage.get(LifecycleStage.ACTIVE.value, []),
                          key=lambda c: c.entity_legal_name.lower())
    active_rows = [card(c) for c in active_cases]

    off = []
    for stage, label in OFF_PIPELINE:
        group = by_stage.get(stage.value, [])
        if group:
            off.append({"label": label, "cases": group, "stage": stage.value})

    # Action queue — plain-English, prioritized. Data-quality flags (humanized) plus
    # aging in-flight cases that carry no flag. This replaces the raw "flag" column.
    stage_label = {s.value: label for s, label in STAGE_ORDER}
    stage_label.update({s.value: label for s, label in OFF_PIPELINE})
    actions = []
    for c in cases:
        for f in c.flags:
            h = humanize_flag(f)
            actions.append({"case": c, **h})
    flagged_ids = {c.case_id for c in cases if c.flags}
    for cd in inflight_cards:
        if cd["stale"] and cd["case"].case_id not in flagged_ids:
            actions.append({
                "case": cd["case"], "severity": "med",
                "title": f"Aging — {cd['days']} days in {stage_label.get(cd['case'].lifecycle_stage, 'stage')}",
                "action": "Follow up to move it forward.", "detail": ""})
    actions.sort(key=lambda a: SEV_ORDER.get(a["severity"], 3))

    in_flight = len(inflight_cards)
    at_risk = sum(1 for cd in inflight_cards if cd["stale"])
    last_synced = max((c.last_synced_at for c in cases if c.last_synced_at), default=None)

    return templates.TemplateResponse(request=request, name="board.html", context={
        "inflight_cards": inflight_cards, "active_rows": active_rows, "off": off,
        "actions": actions,
        "total": len(cases), "active": len(active_cases), "in_flight": in_flight,
        "at_risk": at_risk,
        "last_synced": (last_synced or "")[:16].replace("T", " "),
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
    })


@app.post("/refresh")
def refresh(request: Request):
    """Dashboard 'Refresh' — pull live sources and return to the board.
    A no-op locally until source creds are set; live on Rhollout."""
    try:
        run_sync(reg(), build_sources_from_env(), now_iso())
    except Exception:
        pass  # surfaced on the Sync page; never break the dashboard
    return RedirectResponse(url="/", status_code=303)


ZENDESK_ENV = ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_API_TOKEN")


def zendesk_configured() -> bool:
    return all(os.environ.get(k) for k in ZENDESK_ENV)


async def load_comms(case: Case, parties: list[dict]) -> dict:
    """Load the client's Zendesk ticket thread + macros for the comms panel.
    Live lookup (view-don't-store); degrades to a 'not connected' state when
    creds are absent, and never lets a Zendesk outage break the case page."""
    if not zendesk_configured():
        return {"configured": False, "thread": None, "macros": []}
    try:
        import httpx
        from src.integrations.zendesk_client import ZendeskClient
        email = next((p.get("email") for p in parties
                      if p.get("role") == "borrower_contact" and p.get("email")), None)
        async with httpx.AsyncClient(timeout=30) as http:
            zc = ZendeskClient(http_client=http)
            ticket = await zc.find_ticket_for_client(case.entity_legal_name, email)
            thread = await zc.get_ticket_with_thread(ticket.id) if ticket else None
            macros = await zc.list_macros()
        agent_url = None
        if thread:
            agent_url = (f"https://{os.environ['ZENDESK_SUBDOMAIN']}.zendesk.com"
                         f"/agent/tickets/{thread.ticket.id}")
        return {"configured": True, "thread": thread, "macros": macros, "agent_url": agent_url}
    except Exception as e:
        return {"configured": True, "thread": None, "macros": [], "error": str(e)}


@app.get("/case/{case_id}", response_class=HTMLResponse)
async def case_detail(request: Request, case_id: str):
    r = reg()
    c = r.get_case(case_id)
    if not c:
        return HTMLResponse(f"<p>Case {case_id} not found. <a href='/'>Back</a></p>", status_code=404)
    now = datetime.now(timezone.utc)
    events = list(reversed(r.events_for(case_id)))  # newest first
    parties = r.parties_for(case_id)
    comms = await load_comms(c, parties)

    # legal next stages this case may move to (typed transition rules)
    cur = LifecycleStage(c.lifecycle_stage)
    next_stages = [(s, label) for s, label in ALL_STAGES
                   if s != c.lifecycle_stage and is_allowed_transition(cur, LifecycleStage(s))]

    # Stage tracker: where this case sits along the canonical pipeline.
    canonical = [s for s, _ in STAGE_ORDER]
    off_pipeline = cur not in canonical
    cur_idx = canonical.index(cur) if not off_pipeline else -1
    stepper = []
    for i, (s, label) in enumerate(STAGE_ORDER):
        if off_pipeline:
            status = "off"
        elif i < cur_idx:
            status = "done"
        elif i == cur_idx:
            status = "current"
        else:
            status = "todo"
        stepper.append({"label": label, "status": status})

    return templates.TemplateResponse(request=request, name="case.html", context={ "c": c, "events": events, "parties": parties,
        "stage_label": STAGE_LABELS.get(c.lifecycle_stage, c.lifecycle_stage),
        "days": _days_since(c.stage_entered_at, now),
        "next_stages": next_stages, "stepper": stepper, "off_pipeline": off_pipeline,
        "comms": comms, "zendesk_env": ZENDESK_ENV,
        "flag_items": [humanize_flag(f) for f in c.flags],
        "progress": stage_progress(c.lifecycle_stage),
    })


@app.post("/case/{case_id}/reply")
async def send_client_reply(case_id: str, ticket_id: str = Form(...),
                            body: str = Form(...), public: str = Form("true")):
    """Send a client-facing reply on the case's Zendesk ticket. The human gate:
    the logged-in operator wrote/approved the text and clicked send, so it goes out
    as approved_by=OPERATOR via the sanctioned send_reply() path — never auto-sent."""
    if not (zendesk_configured() and body.strip()):
        return RedirectResponse(url=f"/case/{case_id}", status_code=303)
    import httpx
    from src.integrations.zendesk_client import ZendeskClient
    from src.agents.client_comms_agent import send_reply
    ts = now_iso()
    is_public = public == "true"
    async with httpx.AsyncClient(timeout=30) as http:
        zc = ZendeskClient(http_client=http)
        receipt = await send_reply(zc, ticket_id, body.strip(), approved_by=OPERATOR, public=is_public)
    reg().append_event(
        case_id, ts, OPERATOR, "client_reply_sent", field="zendesk",
        new_value=f"ticket {ticket_id} · {receipt.action}"
                  + (f" · {receipt.comment_id}" if receipt.comment_id else ""),
        evidence_link=f"https://{os.environ['ZENDESK_SUBDOMAIN']}.zendesk.com/agent/tickets/{ticket_id}",
        idempotency_key=f"reply:{case_id}:{ts}")
    return RedirectResponse(url=f"/case/{case_id}", status_code=303)


@app.post("/case/{case_id}/advance")
def advance(case_id: str, new_stage: str = Form(...), note: str = Form("")):
    r = reg()
    c = r.get_case(case_id)
    if not c:
        return HTMLResponse("case not found", status_code=404)
    ts = now_iso()
    updated = Case(case_id=case_id, entity_legal_name=c.entity_legal_name,
                   lifecycle_stage=new_stage)
    r.upsert_case(updated, actor=OPERATOR, ts=ts, evidence_link="webapp:manual-advance")
    if note.strip():
        r.append_event(case_id, ts, OPERATOR, "note", new_value=note.strip(),
                       idempotency_key=f"advnote:{case_id}:{ts}")
    return RedirectResponse(url=f"/case/{case_id}", status_code=303)


@app.post("/case/{case_id}/note")
def add_note(case_id: str, note: str = Form(...),
             next_action: str = Form(""), owner: str = Form("")):
    r = reg()
    c = r.get_case(case_id)
    if not c:
        return HTMLResponse("case not found", status_code=404)
    ts = now_iso()
    if note.strip():
        r.append_event(case_id, ts, OPERATOR, "note", new_value=note.strip(),
                       idempotency_key=f"note:{case_id}:{ts}")
    if next_action.strip():
        upd = Case(case_id=case_id, entity_legal_name=c.entity_legal_name,
                   lifecycle_stage=c.lifecycle_stage,
                   next_action=next_action.strip(),
                   next_action_owner=owner.strip() or None)
        r.upsert_case(upd, actor=OPERATOR, ts=ts, evidence_link="webapp:note")
    return RedirectResponse(url=f"/case/{case_id}", status_code=303)


# ── R7: Monthly Rho<>Webster report ───────────────────────────────────────────
# Preview the list, download the two attachments, read the covering email draft.
# The tool DRAFTS only — sending to Webster is a manual, human step (external gate).

def _default_as_of() -> str:
    return wm.month_end(datetime.now(timezone.utc).date()).isoformat()


def _build_report(as_of: str):
    """Row set + email draft for a given as-of month, with per-row review reasons."""
    r = reg()
    as_of_d = wm.month_end(as_of)
    rows = wm.select_cases(r, as_of_d)
    for row in rows:
        row["completion_display"] = wm.fmt_completion(row["completion"])
        reasons = list(row["flags"])
        if row["status"] in ("Active", "Blocked") and not row["completion"]:
            reasons.append("marked Active/Blocked but no completion date recorded")
        row["review_reasons"] = reasons
    return r, as_of_d, rows


@app.get("/reports/webster", response_class=HTMLResponse)
def webster_report(request: Request, as_of: str = ""):
    as_of = as_of or _default_as_of()
    r, as_of_d, rows = _build_report(as_of)

    # Receipt/audit: record that this month's report was generated (idempotent per month).
    ts = now_iso()
    base = wm.report_basename(as_of_d)
    for row in rows:
        r.append_event(row["case_id"], ts, "report:webster_monthly", "report_generated",
                       field="webster_monthly", new_value=f"{base} [{row['status']}]",
                       evidence_link="report:webster_monthly",
                       idempotency_key=f"webrpt:{row['case_id']}:{as_of_d.isoformat()}")

    return templates.TemplateResponse(request=request, name="reports_webster.html", context={
        "rows": rows,
        "review_rows": [row for row in rows if row["review_reasons"]],
        "email": wm.draft_email(as_of_d),
        "as_of": as_of_d.isoformat(),
        "as_of_display": wm.fmt_completion(as_of_d.isoformat()),
        "basename": base,
        "n_active": sum(1 for row in rows if row["status"] == "Active"),
        "n_blocked": sum(1 for row in rows if row["status"] == "Blocked"),
        "n_inprogress": sum(1 for row in rows if row["status"] == "In progress"),
    })


@app.get("/reports/webster/download")
def webster_download(as_of: str = "", fmt: str = "pdf"):
    as_of = as_of or _default_as_of()
    as_of_d = wm.month_end(as_of)
    rows = wm.select_cases(reg(), as_of_d)
    base = wm.report_basename(as_of_d)
    # Render into a per-request temp dir (contains entity names — never the repo, per
    # the daca-data-security skill; the OS temp dir is outside git).
    out_dir = tempfile.mkdtemp(prefix="daca_webster_")
    if fmt == "xlsx":
        path = wm.render_xlsx(rows, f"{out_dir}/{base}.xlsx", as_of_d)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        path = wm.render_pdf(rows, f"{out_dir}/{base}.pdf", as_of_d)
        media = "application/pdf"
    return FileResponse(path, media_type=media, filename=path.rsplit("/", 1)[-1])


# ── R12: live sync (in-app refresh) ───────────────────────────────────────────
# Pulls Jira + Salesforce + the DACA Summary sheet directly and runs the syncs.
# Sources with no credentials report "not configured" — the app stays usable
# locally on the seeded register without any sync creds set.

def _source_badges() -> list[dict]:
    s = build_sources_from_env()
    return [
        {"name": "DACA Summary sheet", "configured": s.gsheet.configured()},
        {"name": "Jira (CSHELP)", "configured": s.jira.configured()},
        {"name": "Salesforce", "configured": s.salesforce.configured()},
    ]


@app.get("/sync", response_class=HTMLResponse)
def sync_status(request: Request):
    return templates.TemplateResponse(request=request, name="sync.html", context={
        "sources": _source_badges(),
        "runs": last_sync_runs(reg(), limit=10),
        "any_configured": any(b["configured"] for b in _source_badges()),
    })


@app.post("/sync")
def sync_now(request: Request):
    run_sync(reg(), build_sources_from_env(), now_iso())
    return RedirectResponse(url="/sync", status_code=303)


@app.get("/health")
def health():
    r = reg()
    return {"status": "ok", "db": DB_PATH, "cases": len(r.all_cases())}
