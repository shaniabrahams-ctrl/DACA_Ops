# DACA Ops — consolidated context & handoff (2026-07-22)

The single catch-up doc. Read this + the `daca-ops-tool` skill and you have the whole
picture: what's built, the DRI's workflow nuances/decisions, the live example, and the
deploy state. Branch: `claude/nifty-darwin-rle1pt` (all work pushed).

---

## 1. What the tool is (success criteria)

One queryable **register** that is the system of record for every DACA, merged from all
the systems the process lives in, **replacing the DACA Summary g-sheet tracker**; plus a
**guided-expert layer** that walks any Rho ops rep through a DACA end-to-end.
**Success = the Rho team services DACA requests efficiently with minimal manual effort;
human touchpoints are approvals, not corrections. A required manual fix = a tool bug.**

## 2. Workflow nuances & product decisions (from the DRI — capture these)

1. **Replace the tracker.** The register is the master; the g-sheet becomes a generated
   export. The **All DACAs** tab is the tracker-replacement view (search, sort, all
   sources linked).
2. **New requests must be impossible to miss.** Surfaced in-app (the "New requests to
   triage" band) **and** auto-posted to `#daca-ops` Slack. **Internal ops notifications
   are the tool's job — NOT human-gated.** (Do not make the DRI approve each Slack ping.)
3. **Multi-source ingest, including Gmail.** A request that arrives only as an email to
   `daca@rho.co` must flow in — email intake is a first-class source alongside Typeform,
   Jira, Salesforce, the sheet, and Zendesk.
4. **One-click from where the notification lands.** On a new request: one button →
   create the DACA Jira ticket **and** write known info to the tracker.
5. **UI = human-centered dashboard portal.** At-a-glance KPIs; a plain-English **action
   queue** (no engineer jargon like `source_conflict:` shown to reps); **end-to-end
   progress** per DACA (step X/9, what's now, what's next, how many to Active);
   side-by-side scrollable panels; **resolve conflicts in-app** (show every source, let
   the human tell the tool the correct value).
6. **Guided-expert layer (R11).** Walk a new rep through the whole SOP flow; the tool
   drafts comms (exact SOP macros), creates the ticket, updates the tracker;
   **guide-and-gate** the constitutionally-human steps.
7. **Human-approval gate ONLY on outward / external / irreversible actions** — the
   Webster report send, client emails, DocuSign, a live Jira create. Draft-then-human-send
   for anything client- or Webster-facing. Internal register updates + ops notifications
   are automatic.
8. **No-infer discipline.** Never guess borrower entity, lender, or status. Flag for
   confirmation; act only on typed/confirmed data. (Gumloop failed on inference.)
9. **Security (daca-data-security skill).** View-don't-store client PII; minimize what
   goes to Anthropic; secrets never in git; the register DB is gitignored. Decision on
   record: the prefilled-DACA files with PII in git history are **accepted** (Option 3).

## 3. DACA facts that shape the flow (from the SOP)

- 4-party Springing DACA: Rho (Platform) · Webster Bank N.A. (Bank) · Client/Borrower ·
  Lender. **Springing only** (no fully-blocked). **Checking accounts only.**
- Signing order (exact): **Borrower → Lender → Rho CFO (Mike Szarowicz) → Webster
  (Melissa Santos, Exec MD).**
- Redlines discouraged (VIP/high-value/at-risk only; tracked-changes Word, never PDF;
  separate LEGALHELP ticket).
- Turnaround 1–2 weeks after all sign. Trigger event **2-hour** SLA; termination
  **1-business-day** SLA. **Monthly Rho↔Webster report** to the Webster BaaS team.
- Lifecycle stages: inquiry → application_received → fraud_review → templates_sent →
  (redline_review) → compliance_review → docusign → final_setup → active;
  off-pipeline: canceled / rejected / terminated / on_hold / closed_unreconciled.
- SOP source: Notion "Rho DACA Process" `245db9eb-a4f0-800c-816c-cb5a02133f81`.

## 4. Built this session (all pushed)

- **R7 monthly Webster report** — XLSX+PDF + email draft from the register; human sends.
- **Typeform loan-agreement filing** into the client's Drive folder.
- **R12 live sync** — Jira/Salesforce/Sheet **and Gmail** source clients + `/sync` +
  `tools/scheduled_sync.py` (the Rhollout cron); idempotent (polling model).
- **Dashboard redesign** — KPI band, plain-English action queue, side-by-side
  scrollable action-queue | in-flight, per-DACA end-to-end progress, Refresh.
- **All DACAs** tracker-replacement tab (search/sort, source deep-links to Jira/LEGALHELP).
- **In-app conflict resolution** — per-flag Resolve (correct stage + note) + Sources card.
- **Client comms (Zendesk)** — thread view, macros, human-gated reply via `send_reply`.
- **Email intake + New-requests band + auto Slack notifier.**
- **R11 guided walkthrough** — `src/guide/playbook.py` (per-stage SOP steps) + case-page
  "Guided next step" panel; SOP-accurate draft macros; **one-click Create DACA ticket**.
- **Fixes:** control_state clobber; Jira "Canceled" mapping; canceled cases shown; sync idempotency.

Key commits: R7 `2edda6f` · loan-agmt `14c4e9b` · R12 `840dba5` · dashboard `56fd464` ·
Jira links `316b232` · All DACAs+resolve `d570109` · email/Slack `5ba4b42` · Gmail+draft
`dc1f038` · R11 guide `92bb8e5` · one-click `47726bc` · deploy prep `666e541`.

## 5. Live example — Spark Advisors (in the register as `EMAIL-SPARKADVISORS`)

New request 2026-07-21 by email to `daca@rho.co`: Pooneet Kant (COO), re "Control
Agreements — Webster Bank and Interactive Brokers", time-sensitive. Currently at
**inquiry**. Slack alert sent to `#daca-ops`. Next step (per SOP + the guide): draft the
intro/kick-off email (send the DACA request application), then one-click create the Jira
ticket when the Typeform is back.

## 6. Deploy state (Rhollout)

- App **`daca-ops-app1`** created → repo **`UnderTechnologiesLabs/rhollout-daca-ops-app1`**,
  URL `daca-ops-app1.rho-preview.co`. Duplicates (`rho-daca-ops`, `daca-ops-app2`) deleted.
- **DNS** requested in #tech-builder-experience (pending).
- **Secrets** (via `/rhollout secret create` modal): self-serve wave = `JIRA_EMAIL`,
  `JIRA_API_TOKEN`, `TYPEFORM_TOKEN`, `ZENDESK_SUBDOMAIN/EMAIL/API_TOKEN`,
  `ANTHROPIC_API_KEY`, `SLACK_CHANNEL=C0APFKNF8SY`. Admin wave = `SLACK_BOT_TOKEN`,
  `SF_INSTANCE_URL`/`SF_ACCESS_TOKEN`, and the Google service-account JSON (to be named
  **`GOOGLE_SA_JSON`** + `GMAIL_DELEGATED_USER=daca@rho.co` — code reads JSON-from-env,
  wired during the port). `DATABASE_URL` (Postgres) is auto-provided by Rhollout.
- Read-only ops (run on your machine, needs gcloud + Rho login): tail logs / list secret
  names — commands are in the Rhollout DM.

## 7. Next steps (in order)

1. Finish the self-serve secrets; request the 3 admin creds (Slack app, Salesforce OAuth,
   Google service account + Gmail delegation).
2. **Clone `rhollout-daca-ops-app1`** and add it to a Claude session → I move the code in,
   do the **SQLite→Postgres port validated against the real Postgres**, wire the scheduled
   sync cron + the JSON-from-env Google creds, confirm the dashboard loads behind the gateway.
3. Live smoke test: one sync → a new email intake flows to Slack + the board.
4. Then: R8 weekly Download; Salesforce write-back + sheet export; R13 Slack action bot.

## 8. Reference file inventory

Skills (`.claude/skills/`): `daca-ops-tool` (master spec — start here), `daca-data-security`,
`daca-doc-prep`, `daca-doc-currency`, `zendesk-client-comms`.
Docs (`docs/`): this file, `NEXT_SESSION_HANDOFF.md`, `CURRENT_STATE_ASSESSMENT.md`,
`FEASIBILITY_ASSESSMENT.md`, `GUMLOOP_AGENT_REVIEW.md`, `REDESIGN_PROPOSALS.md`,
`DEPLOYMENT_RHOLLOUT.md`, `ZENDESK_INTEGRATION.md`, `ZENDESK_SIGNAL_REFERENCE.md`.
Code: `src/register/` (register, syncs, clients, intake_email, sync_service),
`src/webapp/` (app + templates + draft_reply + humanize), `src/guide/playbook.py`,
`src/integrations/` (zendesk_client, drive_writer, slack_notify), `src/reports/webster_monthly.py`,
`src/agents/`, `src/operations/`; `tools/` (seed_register, scheduled_sync, backfill_loan_agreements).
