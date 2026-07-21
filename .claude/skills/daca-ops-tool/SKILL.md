---
name: daca-ops-tool
description: Master specification for the Rho DACA Operations tool — the single rebuildable reference. Use this whenever building, extending, deploying, or debugging the DACA Ops app (case register, multi-source sync, pipeline board, monthly Webster report, client comms, doc-prep, or the guided-expert layer). Captures every requirement, every data source with its real identifiers, the architecture, the security model, and what is built vs. not-yet-built, so any LLM or engineer can pick it up and continue or rebuild from scratch.
---

# Rho DACA Operations Tool — Master Specification

This is the authoritative, rebuildable spec. If the repo were lost, this document
plus the listed sources is enough to rebuild the tool. It is deliberately
exhaustive about **requirements** and **sources**. Sibling skills/docs hold the
deep detail for specific areas (see "Companion documents").

## 1. Purpose & vision

Two layers:

1. **Unified operational system of record + monitor.** One queryable register of
   every DACA case, merged from all the systems the process actually lives in
   (Google Sheet tracker, Salesforce, Jira, Gmail, Drive). Answers "where is every
   DACA right now, and what's stuck?" and surfaces cross-source conflicts. Replaces
   the overloaded DACA Summary spreadsheet as the master (the sheet becomes a
   generated export).
2. **A DACA "expert" that guides a general Rho Ops rep through a request end to
   end** — intake → fraud/compliance → templates → redline → DocuSign → setup →
   active, and the trigger/termination lifecycle — grounded in Rho's SOPs so
   someone who has never done a DACA can be walked through it correctly. (Layer 1
   is largely built; Layer 2 is specified here and partially built — see §8.)

Design north stars (from the assessment work in `docs/`): **human-in-the-loop, not
autonomous** (constitutionally human steps: CFO signature, compliance attestation,
legal negotiation, trigger/termination decisions); **view-don't-store** for client
data; **every action idempotent and receipted** (the three prior Gumloop agents
failed on duplicates, lost state, and silent failures — see
`docs/GUMLOOP_AGENT_REVIEW.md`).

## 2. Data sources (real identifiers — this is the load-bearing section)

| Source | What it provides | How to reach it | Key |
|---|---|---|---|
| **"Rho DACA Summary" Google Sheet** | THE historical backbone: 48+ rows, lender name/contact/email, account last-4, all dates, notes, Jira links. The only source with lender contacts. | Drive file ID `140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls`; read via Drive API / MCP `read_file_content`. Parse the PRIMARY table only (numbered Business-ID rows); ignore the legacy sub-tables below it. | **Business ID** |
| **Salesforce (Account object)** | Authoritative DACA status/type/agreement date. 46 DACA accounts (31 Effective, 15 Terminated). No lender data. | SOQL: `SELECT Name, Business_ID__c, DACA_Status__c, DACA_Type__c, DACA_Agreement_Date__c FROM Account WHERE DACA_Status__c != null`. Fields: `DACA_Status__c` (Effective/Terminated), `DACA_Type__c` (Springing/Fully Blocked), `DACA_Agreement_Date__c`, `Business_ID__c`. Read-only MCP `query_salesforce`. | `Business_ID__c` |
| **Jira — CSHELP "DACA Request"** | Live pipeline/workflow stage for in-flight cases. | Cloud id `f87c0a5b-9b38-4613-b55d-cbddfc81601c` (`rho.atlassian.net`). JQL `project = CSHELP AND issuetype = "DACA Request"`. Real statuses: Fraud Initial Review, Templates/Agreement Sent, Legal Redline Review, Pre-Webster Package Review, Docusign Sent, Done, Rejected. | ticket key ↔ Business ID via sheet |
| **Jira — LEGALHELP** | Redline/legal-negotiation tickets (e.g. the Section-6(b) redline lane). | Referenced from the sheet's notes (regex `LEGALHELP-\d+`). NOTE: the LEGALHELP project is **permission-restricted** — not readable with the standard Jira token scope. Link by key/URL; don't assume API read access. | key from sheet note |
| **Typeform → "DACA Application Form - Typeform Responses" sheet** | Client intake applications: lender legal name/address/reps, borrower legal name/address/contact, loan agreement upload, transfer method, gov-receivables & multi-account flags. | Drive sheet `1Oog92OTZ5w4Lss-CSVJ-jos8d4Or3K8qu6EQe0EuvtE`; per-case application copies also exist as separate sheets. | match by borrower name/contact |
| **Gmail (`daca@rho.co` + operators)** | Per-case context, open items, blockers, ShareFile version events, client threads. | Multi-query search per case (see `src/context/sources/gmail.py`). Client-facing channel is **Zendesk + Gmail** (distinct from Jira, which is internal tracking). | thread ↔ case by entity/contact |
| **Notion — SOPs & policy** | The knowledge base for the expert layer: DACA process SOPs, Webster Operations Manual, affirmation/compliance packet requirements, trigger & termination playbooks, brand/style. | Notion search/fetch. Key pages: Rho Brand Guidelines `369db9eb-a4f0-814c-b255-d4b22012ad51`, LLM Style Guide `1addb9eb-a4f0-803b-813e-fc7ae5c4950c`, Access Control Policy, Claude Code Secure Usage Guide. | topic |
| **Google Drive — templates & executed docs** | Springing DACA Word template (10.24), executed agreements, redlines, per-case folders (the sheet's legacy table links Drive folders per case). | Drive search/read; per-case folder links in the sheet. | Business ID / entity |
| **DocuSign** | Envelope status for the signing step. | DocuSign MCP (auth required). | envelope id |

**Merge rule:** the sheet is the Business-ID-keyed backbone; Salesforce overlays
authoritative status by Business ID; Jira overlays live pipeline stage by ticket
key onto **in-flight** cases only (never downgrades a sheet/SF-authoritative
Active/Terminated case — a disagreement becomes a `source_conflict` flag). One
Jira ticket can span multiple entity-cases (a single CSHELP ticket often covers
several debtor entities), so `jira_key` is not unique.

## 3. Requirements (what the tool must do)

**Built (see §7):**
- R1. **Case register** — durable, Business-ID-keyed, append-only event log; two
  orthogonal status dimensions (`lifecycle_stage` vs `control_state`) — never
  conflate pipeline position with who controls the funds.
- R2. **Multi-source sync** — sheet + Salesforce + Jira, idempotent, with
  cross-source conflict flags. (Gmail/Drive/Typeform enrichment = partial.)
- R3. **Pipeline board** — "where is every DACA right now", days-in-stage,
  staleness (>30d), needs-attention flags.
- R4. **Net-new intake** — create a case, start its timeline.
- R5. **Case detail** — timeline, parties, flags, advance-stage (typed transition
  rules), set next action.
- R6. **Local web app** — one-command launch; same code deploys to Rhollout.

**Specified, not-yet / partially built:**
- R7. **Monthly Rho↔Webster report** (see §5) — the standing external obligation.
- R8. **Weekly internal "Download"** — the DRI's weekly status summary from the
  register (rollout doc calls this the second workflow).
- R9. **Client comms** on Zendesk + Gmail — draft replies, attachments, SendSafely
  links; human-approval gate on every send (`src/agents/client_comms_agent.py`,
  `src/integrations/zendesk_client.py` exist; not wired to the web app).
- R10. **Doc-prep** — pre-fill the Springing DACA template per entity, with
  version-integrity checks (`daca-doc-prep` skill, `src/operations/prefill_daca.py`).
- R11. **Guided-expert layer** — walk an ops rep through the full process step by
  step, grounded in the Notion SOPs; per-stage checklists, required docs, who to
  contact, what "done" looks like. (The register's `lifecycle_stage` is the spine;
  the SOP content is the guide.)
- R12. **Live "Sync now"** in the app (currently the app reads a register the agent
  seeds; Rhollout runs the sync on a schedule with service creds).

## 4. Architecture

```
src/register/         the system of record
  lifecycle.py        LifecycleStage + ControlState enums; Jira/sheet status maps;
                      allowed-transition rules
  schema.py           SQLite DDL (ports to Rhollout Postgres unchanged):
                      cases, parties, accounts, events(append-only), documents
  db.py               Register data layer — ALL writes go through here; idempotency
                      keys + event logging enforced in one place
  sync_gsheet.py      DACA Summary sheet -> cases (Business-ID backbone)
  sync_salesforce.py  SF overlay by Business ID (status/type/agreement) + reconcile
  sync_jira.py        Jira overlay by ticket key onto in-flight cases
  pipeline.py         board view logic (pure view over the register)
src/webapp/           FastAPI + Jinja2 UI (board / case / intake); Rho-branded
tools/seed_register.py  orchestrates gsheet -> jira -> salesforce from JSON/text snapshots
src/agents/, src/context/, src/compliance/, src/learning/  earlier building blocks
  (case investigator, document version agent, docusign preparer, email drafter,
   signing-authority rules, feedback/style learning) — integrate into the guided layer
```

Data-access decoupling: every `sync_*` takes already-fetched records, so the agent
feeds real data this session and a Rhollout job feeds it later — same code.

## 5. Monthly Rho↔Webster report (R7) — exact spec

- **Cadence:** monthly, first business days of the following month (the end-of-April
  report was sent May 7).
- **Recipients:** To = Webster BaaS contacts **Sttefany Oliveira**
  (stoliveira@websterbank.com), **Sarah Hickey** (shickey@websterbank.com),
  **Kevin Jamison** (kjamison@websterbank.com); **Cc** daca@rho.co. (Confirm the
  current distribution before each send.)
- **Subject:** `Monthly Rho<>Webster DACAs List: end of {Month Year}`
- **Body:** "Hi Webster Team: Please find attached the revised list of Active and
  In-progress Rho<>Webster DACAs as of the end of {Month Year}. Please let me know
  if you have any questions/comments regarding this list. Regards, {name}, {title}"
- **Attachments:** BOTH a PDF and an XLSX named `Rho<>Webster DACAs List - {YYYY-MM-DD}`
  (month-end date).
- **Content / columns:** one row per DACA with status in {**Active, In progress**}
  (exclude Canceled/Rejected/Terminated), columns: **# · Rho ID (= Business ID) ·
  Business Name · Status · DACA Completion (date)**. This is exactly the
  "Rho<>Webster DACAs List" sub-table in the DACA Summary sheet.
- **Source:** generate from the register (`lifecycle_stage in {active, in-flight
  stages}`), not by hand. Human reviews before send (external-facing to the bank).

## 6. Security model (non-negotiable — see `daca-data-security` skill)

- **View, don't store.** The app displays client/lender data pulled from systems of
  record; it does not keep a second persistent copy beyond the register needed to
  operate. Client data is **never committed to git** and **never shipped as a file
  into chat/Anthropic storage**. The register DB is gitignored; code carries no
  client names (docstrings/examples use placeholders).
- **Minimize to Anthropic.** LLM calls get only the fields a task needs, not whole
  records. Account numbers stored as last-4 only; SSNs/full numbers never enter the
  register.
- **Human gate on every outward action** (DocuSign, client email, Jira/SF writes,
  the Webster report). The tool drafts and stages; a human sends.
- Rho's Anthropic data-retention/ZDR terms are **unconfirmed** — treat "minimize"
  as the control that doesn't depend on that answer.

## 7. Build & run

Local (the bridge before Rhollout):
```
git clone -b <branch> <repo> && cd daca_ops
python tools/seed_register.py --gsheet daca_summary.md --jira jira.json --salesforce sf.json
./run_local.sh              # http://127.0.0.1:8000
```
Snapshots (`daca_summary.md`, `jira.json`, `sf.json`) are produced by an
agent/session with the Jira+Salesforce+Drive connectors (see §2 queries), saved
locally, never committed. On Rhollout a scheduled job produces them with service
credentials and the schema targets Postgres. Rhollout setup: see
`docs/DEPLOYMENT_RHOLLOUT.md` (app name `daca-ops`, Python, VPN-only, gateway
locked to named users before real data loads).

## 8. Status: built vs. not-yet

- **Built & verified on live data:** register + event log; sheet/SF/Jira merge
  keyed on Business ID (49 cases); pipeline board; case detail; net-new intake;
  local web app; Rho-branded UI; cross-source conflict flags; LEGALHELP linkage
  by key.
- **Exists but not integrated into the app:** Zendesk client + client-comms agent;
  doc-prep/prefill; document version agent; docusign preparer; signing-authority
  rules; learning/feedback loop.
- **Not yet built:** monthly Webster report generator (R7 — spec in §5, data is all
  in the register); weekly Download (R8); guided-expert walkthrough (R11); live
  "Sync now" (R12); Typeform + Gmail + Drive per-case enrichment; Rhollout deploy.

## Companion documents
- `.claude/skills/daca-data-security/SKILL.md` — the storage/PII architecture.
- `.claude/skills/daca-doc-prep/SKILL.md` — pre-filling the DACA Word doc.
- `.claude/skills/daca-doc-currency/SKILL.md` — auditing SOP/template currency.
- `docs/CURRENT_STATE_ASSESSMENT.md`, `REDESIGN_PROPOSALS.md`,
  `GUMLOOP_AGENT_REVIEW.md`, `FEASIBILITY_ASSESSMENT.md`, `DEPLOYMENT_RHOLLOUT.md`,
  `ZENDESK_INTEGRATION.md` — the grounding analysis.
