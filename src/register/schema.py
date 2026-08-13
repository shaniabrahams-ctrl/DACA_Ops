"""
Case register schema — the durable, queryable source of truth.

This is the backbone from REDESIGN_PROPOSALS.md §1.3: a DACA *case* register with
an append-only event log, replacing the overloaded tracker spreadsheet. The sheet
becomes a generated read-only export; this is the master.

ENGINE NOTE: this iteration uses SQLite (stdlib, zero-dependency) so the tool is
runnable locally against real data today. On Rhollout (DEPLOYMENT_RHOLLOUT.md) the
same schema targets the provisioned Postgres — the DDL is deliberately plain SQL
that ports with minimal change (TEXT timestamps as ISO-8601, no SQLite-only types).
The DATA is always real; only the engine and host differ between local and Rhollout.

Five tables, mirroring the proposal exactly:
  cases     — one row per entity-agreement, the two split status dimensions
  parties   — lender / counsel / borrower contact / signatory, each with a source
  accounts  — masked account refs + RAP state (never full account numbers here)
  events    — APPEND-ONLY audit log: actor, type, field, old->new, evidence link
  documents — doc inventory with sha256 + source link (bytes live in Drive, not here)

The `events` table is what gives the agent its memory (harness model) and makes the
monthly Webster report / weekly Download reproducible as-of any date.
"""

from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cases (
    case_id              TEXT PRIMARY KEY,   -- stable synthetic id (e.g. jira key or entity slug)
    business_id          TEXT,               -- Rho Business ID when known
    entity_legal_name    TEXT NOT NULL,
    lifecycle_stage      TEXT NOT NULL,
    control_state        TEXT NOT NULL DEFAULT 'unknown',
    hold_reason          TEXT,
    tier                 TEXT,
    jira_key             TEXT,   -- NOT unique: one ticket can cover several entity-cases
                                 -- (a single CSHELP ticket often spans multiple debtor entities)
    legal_jira_key       TEXT,
    docusign_envelope_id TEXT,
    drive_folder         TEXT,
    salesforce_ref       TEXT,
    lender_name          TEXT,
    initial_inquiry_date TEXT,
    agreement_date       TEXT,
    completion_date      TEXT,
    termination_date     TEXT,
    next_action          TEXT,
    next_action_owner    TEXT,
    sla_due              TEXT,
    stage_entered_at     TEXT,               -- when the current lifecycle_stage was entered
    last_synced_at       TEXT,
    flags                TEXT                -- JSON array of data-quality/attention flags
);

CREATE TABLE IF NOT EXISTS parties (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id          TEXT NOT NULL REFERENCES cases(case_id),
    role             TEXT NOT NULL,          -- lender|lender_counsel|borrower_contact|signatory|webster
    legal_name       TEXT,
    person           TEXT,
    email            TEXT,
    phone            TEXT,
    address          TEXT,
    verified_against TEXT,                   -- source: 'salesforce'|'application'|'email:<id>'
    UNIQUE(case_id, role, email)
);

CREATE TABLE IF NOT EXISTS accounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      TEXT NOT NULL REFERENCES cases(case_id),
    account_ref  TEXT,                       -- MASKED (last 4 only) — never full numbers
    account_type TEXT,                       -- new_clearing|converted|covered
    rap_state    TEXT,                       -- active|deactivated|blocked
    schedule_a   INTEGER DEFAULT 0,          -- bool: is this the Schedule A account
    UNIQUE(case_id, account_ref)
);

CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       TEXT NOT NULL REFERENCES cases(case_id),
    ts            TEXT NOT NULL,             -- ISO-8601 UTC
    actor         TEXT NOT NULL,             -- 'agent'|'human:<email>'|'webhook:<system>'|'sync:jira'
    event_type    TEXT NOT NULL,             -- stage_change|control_change|field_update|doc_added|note|receipt
    field         TEXT,
    old_value     TEXT,
    new_value     TEXT,
    evidence_link TEXT,                      -- the email/certificate/jira transition backing this
    idempotency_key TEXT UNIQUE              -- dedupe: (source, external_id, change) — see sync layer
);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       TEXT NOT NULL REFERENCES cases(case_id),
    doc_type      TEXT NOT NULL,             -- application|loan_agmt|redline|affirmation|executed_daca|
                                             -- termination_notice|initial_instruction|disposition_instruction
    drive_link    TEXT,
    sha256        TEXT,
    received_date TEXT,
    UNIQUE(case_id, sha256)
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,               -- ISO-8601 UTC, when the run finished
    source   TEXT NOT NULL,               -- 'all' | 'gsheet' | 'jira' | 'salesforce'
    ok       INTEGER NOT NULL,            -- bool: did this source sync succeed
    detail   TEXT                         -- JSON: per-source counts, or the error message
);

-- A signal the intake classifier couldn't confidently call net-new (no-infer rule):
-- no case is opened for it, so it has no home in `cases`/`events`. This table exists
-- solely so a re-run of intake doesn't re-post the same "confirm?" ping (idempotency)
-- and so a human's Yes/No decision (from Slack or the app) has somewhere to land.
CREATE TABLE IF NOT EXISTS pending_signals (
    thread_id        TEXT PRIMARY KEY,        -- Gmail thread id (the source event's natural key)
    detected_at      TEXT NOT NULL,
    requester_email  TEXT,
    requester_name   TEXT,
    subject          TEXT,
    snippet          TEXT,
    candidate_entity TEXT,                    -- best-guess entity name — NEVER auto-applied to a case
    zendesk_url      TEXT,
    reasons          TEXT,                    -- JSON array of why it was flagged ambiguous
    resolved         INTEGER NOT NULL DEFAULT 0,
    resolution       TEXT,                    -- 'opened' | 'dismissed'
    resolved_case_id TEXT,
    resolved_by      TEXT,
    resolved_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_cases_stage ON cases(lifecycle_stage);
CREATE INDEX IF NOT EXISTS idx_events_case ON events(case_id, ts);
CREATE INDEX IF NOT EXISTS idx_parties_case ON parties(case_id);
CREATE INDEX IF NOT EXISTS idx_pending_signals_resolved ON pending_signals(resolved);
"""
