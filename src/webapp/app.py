"""
DACA Ops — local web application.

The clickable app. Same code that deploys to Rhollout; locally it runs against a
SQLite register seeded from real Jira + Salesforce data. Server-rendered HTML
(FastAPI + Jinja2), no JS framework, so it launches with one command and has no
build step.

Screens:
  /                     pipeline board — where every DACA is right now
  /case/{case_id}       case detail — timeline, parties, flags, stage actions
  /intake               net-new DACA request form (the funnel entry point)
  POST /intake          create the case in the register
  POST /case/{id}/advance   move a case to a new lifecycle stage (event-logged)
  POST /case/{id}/note      append a human note (event-logged)

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
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.register.db import Register, Case
from src.register.lifecycle import (
    LifecycleStage, ControlState, is_allowed_transition,
)
from src.register.pipeline import STAGE_ORDER, OFF_PIPELINE, STALE_DAYS, _days_since

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get(
    "DACA_REGISTER_DB",
    str(BASE_DIR.parent.parent / "daca_register.db"),
)

app = FastAPI(title="DACA Ops")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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


@app.get("/", response_class=HTMLResponse)
def board(request: Request):
    r = reg()
    now = datetime.now(timezone.utc)
    cases = r.all_cases()

    columns = []
    for stage, label in STAGE_ORDER:
        group = [c for c in cases if c.lifecycle_stage == stage.value]
        cards = []
        for c in sorted(group, key=lambda x: x.stage_entered_at or ""):
            d = _days_since(c.stage_entered_at, now)
            cards.append({
                "case": c,
                "days": d,
                "stale": d is not None and d > STALE_DAYS,
            })
        columns.append({"stage": stage.value, "label": label, "cards": cards})

    off = []
    for stage, label in OFF_PIPELINE:
        group = [c for c in cases if c.lifecycle_stage == stage.value]
        if group:
            off.append({"label": label, "cases": group, "stage": stage.value})

    flagged = [c for c in cases if c.flags]
    active = sum(1 for c in cases if c.lifecycle_stage == LifecycleStage.ACTIVE.value)
    in_flight = sum(len(col["cards"]) for col in columns
                    if col["stage"] != LifecycleStage.ACTIVE.value)

    return templates.TemplateResponse(request=request, name="board.html", context={ "columns": columns, "off": off, "flagged": flagged,
        "total": len(cases), "active": active, "in_flight": in_flight,
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
    })


@app.get("/case/{case_id}", response_class=HTMLResponse)
def case_detail(request: Request, case_id: str):
    r = reg()
    c = r.get_case(case_id)
    if not c:
        return HTMLResponse(f"<p>Case {case_id} not found. <a href='/'>Back</a></p>", status_code=404)
    now = datetime.now(timezone.utc)
    events = list(reversed(r.events_for(case_id)))  # newest first
    parties = r.parties_for(case_id)

    # legal next stages this case may move to (typed transition rules)
    cur = LifecycleStage(c.lifecycle_stage)
    next_stages = [(s, label) for s, label in ALL_STAGES
                   if s != c.lifecycle_stage and is_allowed_transition(cur, LifecycleStage(s))]

    return templates.TemplateResponse(request=request, name="case.html", context={ "c": c, "events": events, "parties": parties,
        "stage_label": STAGE_LABELS.get(c.lifecycle_stage, c.lifecycle_stage),
        "days": _days_since(c.stage_entered_at, now),
        "next_stages": next_stages,
    })


@app.get("/intake", response_class=HTMLResponse)
def intake_form(request: Request):
    return templates.TemplateResponse(request=request, name="intake.html", context={})


@app.post("/intake")
def intake_submit(
    entity_legal_name: str = Form(...),
    lender_name: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    jira_key: str = Form(""),
    notes: str = Form(""),
):
    r = reg()
    ts = now_iso()
    # net-new requests enter at application_received (a request has arrived; the
    # application/typeform is the next gate). case_id = jira key if given, else a
    # slug of the entity name so it's stable and human-readable.
    slug = jira_key.strip() or ("NEW-" + "".join(
        ch for ch in entity_legal_name.upper() if ch.isalnum())[:20])
    case = Case(
        case_id=slug,
        entity_legal_name=entity_legal_name.strip(),
        lifecycle_stage=LifecycleStage.APPLICATION_RECEIVED.value,
        control_state=ControlState.UNKNOWN.value,
        lender_name=lender_name.strip() or None,
        jira_key=jira_key.strip() or None,
        initial_inquiry_date=ts[:10],
        stage_entered_at=ts,
        last_synced_at=ts,
    )
    r.upsert_case(case, actor=OPERATOR, ts=ts, evidence_link="intake:webapp")
    if contact_email.strip():
        r.upsert_party(slug, role="borrower_contact", person=contact_name.strip(),
                       email=contact_email.strip(), verified_against="intake:webapp")
    if notes.strip():
        r.append_event(slug, ts, OPERATOR, "note", new_value=notes.strip(),
                       idempotency_key=f"intakenote:{slug}:{ts}")
    return RedirectResponse(url=f"/case/{slug}", status_code=303)


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


@app.get("/health")
def health():
    r = reg()
    return {"status": "ok", "db": DB_PATH, "cases": len(r.all_cases())}
