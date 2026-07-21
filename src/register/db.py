"""
Register data-access layer — thin, typed, idempotent.

Everything that writes to the register goes through here so the two hard-won
harness properties from GUMLOOP_AGENT_REVIEW.md are enforced in ONE place:

  1. Idempotency — every event carries an idempotency_key; re-applying the same
     sync produces zero new rows (fixes the duplicate-notification / duplicate-row
     failure class, review items #2 and Part D).
  2. Receipts + audit — every state change appends an event with actor + evidence;
     nothing mutates a case field without leaving a trail (review item #4).

No ORM, no external deps — sqlite3 from stdlib. Same SQL targets Postgres on
Rhollout with the connection swapped.
"""

from __future__ import annotations
import sqlite3
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Any

from src.register.schema import SCHEMA_SQL
from src.register.lifecycle import LifecycleStage, ControlState, is_allowed_transition


@dataclass
class Case:
    case_id: str
    entity_legal_name: str
    lifecycle_stage: str
    control_state: str = ControlState.UNKNOWN.value
    business_id: Optional[str] = None
    hold_reason: Optional[str] = None
    tier: Optional[str] = None
    jira_key: Optional[str] = None
    legal_jira_key: Optional[str] = None
    docusign_envelope_id: Optional[str] = None
    drive_folder: Optional[str] = None
    salesforce_ref: Optional[str] = None
    lender_name: Optional[str] = None
    initial_inquiry_date: Optional[str] = None
    agreement_date: Optional[str] = None
    completion_date: Optional[str] = None
    termination_date: Optional[str] = None
    next_action: Optional[str] = None
    next_action_owner: Optional[str] = None
    sla_due: Optional[str] = None
    stage_entered_at: Optional[str] = None
    last_synced_at: Optional[str] = None
    flags: list[str] = field(default_factory=list)


class Register:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # ---- events (append-only) ----

    def append_event(self, case_id: str, ts: str, actor: str, event_type: str,
                     field: Optional[str] = None, old_value: Optional[str] = None,
                     new_value: Optional[str] = None, evidence_link: Optional[str] = None,
                     idempotency_key: Optional[str] = None) -> bool:
        """Append an event. Returns True if written, False if the idempotency_key
        already existed (duplicate suppressed). This is the single dedupe primitive."""
        try:
            self.conn.execute(
                "INSERT INTO events (case_id, ts, actor, event_type, field, old_value, "
                "new_value, evidence_link, idempotency_key) VALUES (?,?,?,?,?,?,?,?,?)",
                (case_id, ts, actor, event_type, field, old_value, new_value,
                 evidence_link, idempotency_key),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # idempotency_key collision — already recorded

    def events_for(self, case_id: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM events WHERE case_id=? ORDER BY ts, id", (case_id,))
        return [dict(r) for r in cur.fetchall()]

    def events_between(self, start_iso: str, end_iso: str) -> list[dict]:
        cur = self.conn.execute(
            "SELECT * FROM events WHERE ts >= ? AND ts <= ? ORDER BY ts, id",
            (start_iso, end_iso))
        return [dict(r) for r in cur.fetchall()]

    # ---- cases ----

    def get_case(self, case_id: str) -> Optional[Case]:
        cur = self.conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_case(row)

    def get_case_by_jira(self, jira_key: str) -> Optional[Case]:
        cur = self.conn.execute("SELECT * FROM cases WHERE jira_key=?", (jira_key,))
        row = cur.fetchone()
        return self._row_to_case(row) if row else None

    def all_cases(self) -> list[Case]:
        cur = self.conn.execute("SELECT * FROM cases ORDER BY case_id")
        return [self._row_to_case(r) for r in cur.fetchall()]

    def upsert_case(self, case: Case, actor: str, ts: str,
                    evidence_link: Optional[str] = None) -> list[str]:
        """
        Insert or update a case, appending an event for each meaningful change.
        Returns the list of human-readable changes applied (empty on no-op).
        Enforces allowed lifecycle transitions — an illegal stage change is
        recorded as a flagged event, not silently applied.
        """
        existing = self.get_case(case.case_id)
        changes: list[str] = []

        if existing is None:
            self.conn.execute(
                """INSERT INTO cases (case_id, business_id, entity_legal_name, lifecycle_stage,
                   control_state, hold_reason, tier, jira_key, legal_jira_key, docusign_envelope_id,
                   drive_folder, salesforce_ref, lender_name, initial_inquiry_date, agreement_date,
                   completion_date, termination_date, next_action, next_action_owner, sla_due,
                   stage_entered_at, last_synced_at, flags)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (case.case_id, case.business_id, case.entity_legal_name, case.lifecycle_stage,
                 case.control_state, case.hold_reason, case.tier, case.jira_key, case.legal_jira_key,
                 case.docusign_envelope_id, case.drive_folder, case.salesforce_ref, case.lender_name,
                 case.initial_inquiry_date, case.agreement_date, case.completion_date,
                 case.termination_date, case.next_action, case.next_action_owner, case.sla_due,
                 case.stage_entered_at, case.last_synced_at, json.dumps(case.flags)),
            )
            self.conn.commit()
            self.append_event(case.case_id, ts, actor, "case_created",
                              new_value=case.entity_legal_name, evidence_link=evidence_link,
                              idempotency_key=f"create:{case.case_id}")
            changes.append(f"created ({case.lifecycle_stage})")
            return changes

        # diff tracked fields
        tracked = ["lifecycle_stage", "control_state", "lender_name", "jira_key",
                   "agreement_date", "completion_date", "termination_date",
                   "next_action", "next_action_owner", "sla_due", "hold_reason", "tier",
                   "docusign_envelope_id", "drive_folder", "salesforce_ref"]
        for f in tracked:
            old = getattr(existing, f)
            new = getattr(case, f)
            if new is None or new == old:
                continue
            if f == "lifecycle_stage":
                if not is_allowed_transition(LifecycleStage(old), LifecycleStage(new)):
                    # record the attempt, flag it, but DO apply (Jira is source of truth
                    # for stage) — the flag surfaces it for human review rather than
                    # silently accepting or silently blocking.
                    self._add_flag(case.case_id, f"illegal_transition:{old}->{new}")
                    self.append_event(case.case_id, ts, actor, "flag",
                                      field="lifecycle_stage", old_value=old, new_value=new,
                                      evidence_link=evidence_link,
                                      idempotency_key=f"illegaltrans:{case.case_id}:{old}:{new}")
                self.conn.execute("UPDATE cases SET stage_entered_at=? WHERE case_id=?",
                                  (ts, case.case_id))
            self.conn.execute(f"UPDATE cases SET {f}=? WHERE case_id=?", (new, case.case_id))
            self.append_event(case.case_id, ts, actor, "field_update", field=f,
                              old_value=str(old), new_value=str(new), evidence_link=evidence_link,
                              idempotency_key=f"upd:{case.case_id}:{f}:{new}")
            changes.append(f"{f}: {old} -> {new}")

        self.conn.execute("UPDATE cases SET last_synced_at=? WHERE case_id=?", (ts, case.case_id))
        self.conn.commit()
        return changes

    def resolve_flag(self, case_id: str, flag: str, actor: str, ts: str,
                     note: Optional[str] = None, new_stage: Optional[str] = None) -> None:
        """Human resolution of an attention flag. Optionally corrects the stage to the
        value the human says is right (applied directly — an explicit human correction
        is authoritative, so it is NOT re-checked against the transition guard), removes
        the flag, and records both as append-only events. This is how a rep tells the
        tool the correct answer for a source-conflict / data-quality flag."""
        c = self.get_case(case_id)
        if not c:
            return
        if new_stage and new_stage != c.lifecycle_stage:
            self.conn.execute(
                "UPDATE cases SET lifecycle_stage=?, stage_entered_at=? WHERE case_id=?",
                (new_stage, ts, case_id))
            self.append_event(case_id, ts, actor, "stage_corrected", field="lifecycle_stage",
                              old_value=c.lifecycle_stage, new_value=new_stage,
                              idempotency_key=f"correct:{case_id}:{ts}")
        if flag in c.flags:
            c.flags.remove(flag)
            self.conn.execute("UPDATE cases SET flags=? WHERE case_id=?",
                              (json.dumps(c.flags), case_id))
        self.append_event(case_id, ts, actor, "flag_resolved", field="flag",
                          old_value=flag, new_value=(note or "resolved"),
                          idempotency_key=f"resolve:{case_id}:{ts}")
        self.conn.commit()

    def _add_flag(self, case_id: str, flag: str) -> None:
        c = self.get_case(case_id)
        if c and flag not in c.flags:
            c.flags.append(flag)
            self.conn.execute("UPDATE cases SET flags=? WHERE case_id=?",
                              (json.dumps(c.flags), case_id))
            self.conn.commit()

    # ---- parties / documents ----

    def upsert_party(self, case_id: str, role: str, **kw) -> None:
        cols = ["legal_name", "person", "email", "phone", "address", "verified_against"]
        vals = {k: kw.get(k) for k in cols}
        try:
            self.conn.execute(
                "INSERT INTO parties (case_id, role, legal_name, person, email, phone, "
                "address, verified_against) VALUES (?,?,?,?,?,?,?,?)",
                (case_id, role, vals["legal_name"], vals["person"], vals["email"],
                 vals["phone"], vals["address"], vals["verified_against"]),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            self.conn.execute(
                "UPDATE parties SET legal_name=?, person=?, phone=?, address=?, verified_against=? "
                "WHERE case_id=? AND role=? AND email=?",
                (vals["legal_name"], vals["person"], vals["phone"], vals["address"],
                 vals["verified_against"], case_id, role, vals["email"]))
            self.conn.commit()

    def parties_for(self, case_id: str) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM parties WHERE case_id=?", (case_id,))
        return [dict(r) for r in cur.fetchall()]

    def add_document(self, case_id: str, doc_type: str, sha256: str,
                     drive_link: Optional[str] = None, received_date: Optional[str] = None) -> bool:
        try:
            self.conn.execute(
                "INSERT INTO documents (case_id, doc_type, drive_link, sha256, received_date) "
                "VALUES (?,?,?,?,?)", (case_id, doc_type, drive_link, sha256, received_date))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def _row_to_case(self, row: sqlite3.Row) -> Case:
        d = dict(row)
        d["flags"] = json.loads(d.get("flags") or "[]")
        return Case(**d)
