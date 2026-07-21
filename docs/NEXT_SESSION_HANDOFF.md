# Next-session handoff — continuing the DACA Ops build

**Read first:** `.claude/skills/daca-ops-tool/SKILL.md` (the master spec — every
requirement, source identifier, and the architecture). This doc is the *how to
continue* companion: the exact next build steps for the four not-yet items, how to
get real data into a fresh session, and known loose ends.

Branch: `claude/nifty-darwin-rle1pt` (all work pushed). Model used: claude-opus-4-8.

---

## 0. Orient a fresh session (do this first, ~5 min)

1. Read `.claude/skills/daca-ops-tool/SKILL.md` and `.claude/skills/daca-data-security/SKILL.md`.
2. **Re-seed the register with live data** (the DB is gitignored — it holds real
   client data — so each session rebuilds it). Using the connected MCP tools:
   - **Jira** (cloud id `f87c0a5b-9b38-4613-b55d-cbddfc81601c`): run JQL
     `project = CSHELP AND issuetype = "DACA Request" ORDER BY updated DESC`,
     fields `key,summary,status,created,updated,labels,assignee`; save raw JSON → `jira.json`.
   - **Salesforce**: SOQL `SELECT Name, Business_ID__c, DACA_Status__c, DACA_Type__c,
     DACA_Agreement_Date__c FROM Account WHERE DACA_Status__c != null`; save → `sf.json`.
   - **Google Drive**: `read_file_content` on sheet
     `140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls`; save the markdown → `daca_summary.md`.
   - Then: `python tools/seed_register.py --gsheet daca_summary.md --jira jira.json --salesforce sf.json`
   - These snapshot files contain real client data → keep them in the scratchpad,
     never commit (already covered by `.gitignore` for `*.db`; do not add the JSON/MD either).
3. `./run_local.sh` → http://127.0.0.1:8000 to see current state (49 cases).

Auth caveats to expect: Atlassian & Salesforce MCP need the user authorized in
claude.ai connectors; LEGALHELP Jira project is permission-restricted (link by
key/URL only). soffice/LibreOffice is broken in the sandbox (can't render docx/pdf
locally) — use PyMuPDF/python-docx and verify structurally.

---

## R7. Monthly Rho↔Webster report generator (recommended first — data already exists)

**Goal:** generate the monthly bank report from the register. Full spec in
SKILL.md §5. This is the standing external obligation and is mostly a query + two
file renders.

**Build steps:**
1. New module `src/reports/webster_monthly.py`:
   - `select_cases(reg, as_of_date)` → cases where `lifecycle_stage` in the
     "reportable" set = **active** + in-flight stages (fraud_review, templates_sent,
     redline_review, compliance_review, docusign, final_setup,
     application_received). Exclude canceled/rejected/terminated. (The sheet's own
     "Rho<>Webster DACAs List" sub-table = Active + In progress — match that.)
   - Columns per row: `# · Rho ID (business_id) · Business Name (entity_legal_name)
     · Status · DACA Completion (completion_date or blank)`. Map internal
     lifecycle → the bank-facing status label ("Active" / "In progress").
   - `render_xlsx(rows, path)` using `openpyxl`; `render_pdf(rows, path)` using
     `reportlab` (the real prior report was ReportLab-generated — match the plain
     tabular look). Filenames: `Rho<>Webster DACAs List - {YYYY-MM-DD}` (month-end).
   - `draft_email(month_year)` → returns subject/body/recipients per SKILL.md §5.
     Recipients: stoliveira@, shickey@, kjamison@ (websterbank.com), cc daca@rho.co.
     **Do not send** — return a draft for human review (external-to-bank = hard gate).
2. Add a web route `/reports/webster` that previews the table and offers the two
   file downloads + the email draft text (the `downloads` capability if artifact,
   or FastAPI FileResponse locally).
3. Log a `report_generated` event per case included (receipt/audit).

**Verify:** row set matches the sheet's Rho<>Webster sub-table for the same
as-of date; open the xlsx/pdf; confirm the email draft is exact.
**Gotchas:** `reportlab`/`openpyxl` aren't in requirements yet — add them.
Confirm the current Webster distribution list before any real send.

---

## R8. Weekly internal "Download"

**Goal:** the DRI's weekly status summary from the register (rollout doc's second
workflow). Internal, not bank-facing.

**Build steps:**
1. `src/reports/weekly_download.py`:
   - Sections: (a) stage changes in the last 7 days (from the `events` table —
     `events_between(start,end)` already exists), (b) stale in-flight cases (>30d in
     stage), (c) open `source_conflict`/attention flags, (d) new intakes, (e) what's
     waiting-on-Rho vs waiting-on-client/lender (from `next_action_owner`).
   - `render_markdown()` for Slack, and reuse for a web route `/reports/weekly`.
2. Optional: post to Slack via MCP (human-approve first; the assessment warns about
   noisy bot posts eroding trust — keep it crisp).

**Verify:** run against the seeded register; counts reconcile with the board.
**Gotcha:** dedupe so the same stale case isn't re-alarmed every week without
change (the Gumloop duplicate-alert failure) — key on (case, flag, week).

---

## R11. Guided-expert walkthrough (the "DACA expert" layer — biggest piece)

**Goal:** walk a general Ops rep through a DACA end-to-end, grounded in the SOPs.
The register's `lifecycle_stage` is the spine; the SOP content is the guide.

**Build steps:**
1. **Harvest the SOP knowledge into a versioned playbook** (do NOT hardcode from
   memory — pull from Notion each build): for each `LifecycleStage`, capture from
   the Notion DACA SOPs + Webster Operations Manual: entry criteria, the exact
   actions/checklist, required documents, who to contact (Rho Legal / Webster BaaS /
   compliance), templates to use, common pitfalls, and the "definition of done"
   that gates the next stage. Store as `src/guide/playbook.py` (structured dict per
   stage) or markdown under `docs/playbook/`. Cross-check against
   `daca-doc-currency` skill so it stays current.
   - Search Notion for: DACA SOP, Webster Operations Manual, affirmation vs
     compliance packet, trigger event playbook, termination playbook, fraud review,
     Typeform/application step, DocuSign step, account setup (RAP).
2. **Per-stage guide panel** on the case detail page: given a case's current stage,
   render the playbook step — checklist (persist checkbox state as events),
   required docs (link to Drive / the doc-prep skill), the drafts available
   (client-comms agent for the email, prefill for the doc), and the "to advance,
   confirm X" gate.
3. **"Start a new DACA" guided flow**: intake → then the tool leads the rep stage
   by stage, only surfacing the next actions, wiring in the already-built pieces
   (case investigator, version gatekeeper, docusign preparer, client-comms agent).
4. Ground every instruction with a source link (Notion page / SOP) so it's
   auditable and updatable — never free-text legal/process advice without a cited
   SOP behind it.

**Verify:** pick a real in-flight case (e.g. one in redline_review) and confirm the
guide shows the correct next step, contacts, and docs matching the SOP.
**Gotchas:** the process has genuine ambiguities (affirmation vs packet regime;
trigger role-reversal legality) flagged in `docs/FEASIBILITY_ASSESSMENT.md` — the
guide must say "confirm with Legal/compliance" at those points, not invent an
answer. Constitutionally-human steps (signature, attestation, negotiation,
trigger/termination decisions) are guide-and-gate, never automate.

---

## R12. Live "Sync now" (in-app refresh)

**Goal:** replace agent-seeded data with a button/scheduled refresh that pulls
live sources itself.

**Build steps:**
1. Write real source clients under `src/register/clients/` implementing the
   fetch each `sync_*` expects: Jira (Atlassian REST + API token), Salesforce
   (connected-app OAuth, read-only), Google Sheets (service account). Same record
   shapes the syncs already consume — so `sync_gsheet/salesforce/jira` are unchanged.
2. `/sync` route (and a scheduled job on Rhollout) that calls the clients then the
   syncs, inside one transaction, and writes a `sync_run` receipt.
3. Local dev reads creds from a `.env` (gitignored); Rhollout from Secret Manager
   (`/rhollout secret create`). This is the step that makes the tool run without an
   agent in the loop — pairs with the Rhollout deploy (`docs/DEPLOYMENT_RHOLLOUT.md`).

**Verify:** `/sync` produces the same register the seed script does; re-run is
idempotent (0 duplicate events).
**Gotcha:** MCP tools are agent-only — a deployed service needs its own service
credentials; do not try to call MCP from the FastAPI process.

---

## Loose ends / known issues to clean up

- **`Apomaya "Lokker"` shows an `illegal_transition` flag** (application_received →
  templates_sent) — harmless artifact of seeding "In progress" sheet rows at a
  neutral stage before the Jira overlay advances them. Consider initializing
  in-progress sheet rows to a truer stage, or suppressing that specific flag.
- **Multi-entity Jira overlay hits only one of the shared-ticket cases**
  (`get_case_by_jira` returns one row). Fine today (siblings are sheet-authoritative)
  but revisit when Jira drives in-flight multi-entity tickets (e.g. Anonos ×3).
- **`sf_unmatched` / Salesforce lag**: recent cases active in the sheet but not yet
  in SF's DACA fields are intentionally not flagged (noise reduction). If SF should
  be kept in lockstep, add a separate low-priority "SF out of date" hygiene view.
- **LEGALHELP API access** — request read scope for the LEGALHELP Jira project if
  live legal-ticket status is wanted (currently key/URL link only).
- **`docs/prefilled_dacas/*.docx` still contain real signer PII in git history**
  (from before the security skill) — the git-history cleanup decision is still open
  (see the daca-data-security skill's "Known violation" section). Three options
  given there; needs the DRI's call.
- **Rhollout not yet provisioned** — the app runs locally only until then.
- **requirements.txt** will need `reportlab`, `openpyxl` (R7) and real source-client
  libs (R12) added.

## Suggested order
R7 (fast, external obligation, data ready) → R12 (unlocks standalone running +
pairs with Rhollout) → R8 (quick once R7 patterns exist) → R11 (largest; the
expert layer — do after the data/refresh foundation is solid).
