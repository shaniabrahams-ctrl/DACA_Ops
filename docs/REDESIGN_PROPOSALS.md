# DACA Ops — Redesign Proposals (Tracker · Weekly Update · Intake Form · DocuSign)

**Date:** 2026-06-10 · **Status:** Proposals for review — nothing here is implemented yet.
**Grounding:** DACA Summary spreadsheet (full read), #daca-applications channel history (C03HU7P6ENL), saved Typeform question list ("DACA Typeform questions" doc, Drive), DocuSign developer documentation, Gumloop agent handoff brief.

---

## 1. Tracking System Redesign

### 1.1 What the current spreadsheet actually contains (observed)

The DACA Summary sheet (`140z-O_Zo…`) is several generations of tracker layered in one file:

- **A current 2026 register** (~44 rows) — the only actively maintained surface.
- **A stale "report" tab** that contradicts it (Edwards entities still "In progress" there; executed 5/8–5/21 on the main tab).
- **Legacy 2022–23 tabs** from the Evolve era (different columns: AM, old/new account numbers, amendment tracking) with their own conflicting statuses (Kaged "Blocked by Lender" vs main tab "Blocked "; Mad Rabbit "ACTIVE" in one legacy tab, "Terminated 11/15" in another).
- **A user-access tab** (account access per client/lender) that is point-in-time and unmaintained.

### 1.2 Specific defects (all verifiable in the sheet today)

| # | Defect | Example |
|---|---|---|
| 1 | **Duplicate live rows** | POST ACUTE ANALYTICS appears twice: row 38 ("Fraud Initial Review") and row 43 ("Active", executed 5/26) |
| 2 | **One Status column encoding two different dimensions** | "Active/Blocked/TERMINATED" (account control state) mixed with "In progress/Pending Kick-off/Fraud Initial Review" (pipeline stage) — so a triggered-but-live DACA and a mid-pipeline application are indistinguishable in queries |
| 3 | **No audit trail** | Cells are overwritten in place; no record of who changed what when — not audit-ready for a banking-partner-facing register |
| 4 | **Sparse mandatory data** | Lender name/contact blank on most in-progress rows (rows 29–44); "Initial Inquiry" almost never populated; "Business UBO" column entirely empty |
| 5 | **Impossible/inconsistent dates** | LOOPS BEAUTY: Agreement Date Apr/16/2024 *after* Completion Date Apr/1/2024; Canvas Medical has Completion but no Agreement Date; three date formats coexist ("Aug/29/2023", "5/21", "May/15/2026") |
| 6 | **Multi-account entities crammed into one cell** | Axis Global: "0965 and 5306" — unqueryable, and exactly the multi-account structure the trigger playbook says is operationally hardest |
| 7 | **Free-text Note column as the de-facto case history** | Notes carry redline state, legal tickets, client sentiment, policy decisions ("Do not want to approve client like this…") — un-reportable and lossy |
| 8 | **Stale rows that contradict reality** | CAP 31st Avenue: note says "ticket closed on 5/5" but Status still "In progress" |
| 9 | **Sensitive data exposure pattern** | Legacy tabs hold full account numbers; current tab last-4 — no consistent masking policy in a widely-shared sheet |
| 10 | **Reporting is manual re-derivation** | The monthly Webster list and the weekly Download are both hand-assembled from this sheet (May's termination exclusion was handled from memory) |

### 1.3 Target design: a case register, not a list

The unit of record should be the **DACA Case** (one per entity-agreement), with related tables instead of overloaded columns:

```
cases        — case_id, business_id, entity_legal_name, lifecycle_stage,
               control_state, hold_reason, tier, jira_key, legal_jira_key,
               docusign_envelope_id, drive_folder, salesforce_ref,
               initial_inquiry_date, agreement_date, completion_date,
               termination_date, next_action, next_action_owner, sla_due
parties      — case_id, role (lender|lender_counsel|borrower_contact|signatory…),
               legal_name, person, email, phone, address, verified_against (source)
accounts     — case_id, account_ref (masked), account_type (new_clearing|converted|covered),
               rap_state (active|deactivated|blocked), schedule_a (bool)
events       — case_id, timestamp, actor (human|agent|webhook), event_type,
               field, old_value, new_value, evidence_link   ← APPEND-ONLY
documents    — case_id, doc_type (application|loan_agmt|affirmation|executed_daca|
               termination_notice…), drive_link, sha256, received_date
```

**Two separate status dimensions**, finally split:
- `lifecycle_stage`: Inquiry → Application Received → Fraud Review → Templates Sent → (Redline Review) → Affirmation/Compliance → DocuSign → Final Setup → **Active** → Terminated (+ On Hold / Rejected as flags, mirroring the Jira forward-only flow).
- `control_state`: Borrower-Controlled → Lender-Controlled (Triggered) → Released/Terminated.

**Why this wins on your four criteria:**
- **Durability** — the register lives in a database behind the DACA Ops app (the sheet becomes a generated, read-only export, not the master).
- **Consistency** — stages are an enum validated against the SOP's allowed transitions; dates are ISO and machine-checked (no more completion-before-agreement).
- **Traceability** — the append-only `events` table is the audit log: every change carries actor + source evidence link (the email, the DocuSign certificate, the Jira transition). This also gives the agent its "memory" per the harness model.
- **Audit-ready reporting** — the monthly Webster list, the weekly Download, and an examiner-grade case file (all documents + full event history per case) become **views generated from the register**, not hand-built artifacts. Terminations are included/excluded by rule, not memory.

### 1.4 Interim hygiene (this week, zero build cost)
1. Dedupe POST ACUTE (keep row 43, delete row 38 after porting its note).
2. Split Status into two columns (`Stage`, `Control State`) with data-validation dropdowns.
3. Normalize dates to `YYYY-MM-DD`; fix the LOOPS inversion; backfill Canvas's agreement date from the DocuSign certificate.
4. Move legacy tabs to a separate "ARCHIVE — do not edit" spreadsheet.
5. Add `Next Action / Owner / Due` columns — the three questions every status inquiry is actually asking.
6. Turn on sheet edit history notifications + protect the header/validation ranges.

---

## 2. Weekly Slack Update ("DACA Download") Redesign

### 2.1 What the history shows (C03HU7P6ENL, March–June 2026)

- Cadence has drifted: 3/17, 3/25, 4/1, 4/8, 4/15, 4/29, 5/22 — then **nothing for ~3 weeks** (as of 6/10). The Gumloop Friday-10am draft schedule exists but isn't reliably producing posts.
- Format mutates week to week (title, section names, tier labels, nesting), so readers can't pattern-match.
- The post is an **inventory** (everything in progress) rather than a **delta** (what changed, what's stuck, who's needed) — so it's long, and stakeholders still ask ad-hoc ("is there anywhere I can check to see the status of this?" — Lucas Dondertman, 4/27).
- Real wins are buried (the Unshaken/NHJM trigger events with met SLAs were excellent content, formatted as afterthought sub-bullets).

### 2.2 Redesign principle: split "always-current state" from "weekly change"

Slack is a terrible database and a great changelog. So:

1. **Always-current state** lives in a **pinned, auto-updated surface** — a Slack canvas in the channel (or the DACA Ops app dashboard link once built), regenerated from the case register on every change. This permanently answers the "where can I check status?" question. No more status archaeology.
2. **The weekly Download becomes a short delta post** — what moved, what's blocked and on whom, what needs a decision — with the full pipeline one click away.

### 2.3 Proposed format (Slack-native: short top message + threaded detail)

**Top-level message (the only thing most people read):**

> **DACA Download — week of Jun 8** · 7 in flight / 27 active / 1 terminated YTD
> 🟢 **Moved:** Post Acute Analytics **executed 5/26** 🎉 · Bud DocuSign re-sent, with borrower signer
> 🔴 **Blocked — needs action:**
> • **Anonos (2 entities, $4.5M)** — redlines with **Webster Legal since 6/8**, client closing imminent → *escalation call w/ Sttef if no reply by EOD Wed*
> • **FINALIS** — in Fraud review since 6/5 → *@fraud-team, ETA?*
> ⚪ **Stalled >30d:** Lokker (no client reply since 3/26 — final nudge then auto-hold) · CAP 31st (on-hold candidate)
> 📌 Full pipeline & per-case history: [pinned canvas/dashboard]

**In-thread (for those who want depth):** one reply per section — full pre-DocuSign list with days-in-stage and waiting-on, completions detail, terminations detail, product/process notes (e.g., the savings→DACA transfer limitation discussion).

**Format rules (stable, machine-fillable):**
- Lead with counts + the celebration; **blocked items always name the owner and the proposed unblock action with a date** — an update that doesn't ask for anything specific changes nothing.
- "Days in stage" and "waiting on" come straight from the case register — never typed by hand.
- Tier labels only from the register (never invented — keeps the Gumloop anti-fabrication rule).
- Same emoji/section skeleton every single week; omit empty sections.
- Agent drafts Friday 10am from the register's event log → DM to you for approval → posts on your 👍 (human-verify gate preserved). If you don't act by Monday 10am, it re-pings rather than silently skipping a week — **cadence is enforced by the harness, not by memory.**

---

## 3. Intake ("DACA Request Application") Redesign

### 3.1 Current form (grounded — full question list from the saved copy)

Lender legal name · lender address · # lender reps with account access · rep name/phone/email (×3, with visible duplication bugs — "1st/2nd representative" blocks repeat) · does Borrower have a Rho account · legal business name · business address · business contact name/email · loan agreement upload · referral · government receivables? · more than one deposit account? · preferred transfer method · anything else.

### 3.2 The mismatch

The form is ~60% lender-contact directory, yet the process's actual downstream needs are chased manually afterwards, every time:

| Information the team chases later | Evidence |
|---|---|
| Single vs multiple Rho entities | Your own intro macro has to ask this in prose (Gumloop handoff §10.1); Edwards/Anonos/FINALIS were all multi-entity discoveries |
| New clearing account vs convert existing (and *which* existing account) | Drives the entire Phase 5 branch + Schedule A; not asked |
| Borrower signatory (name/title/email, is it the registered Control Person?) | "waiting for client confirmation of using existing UBO/CP as signer" (5/22 Download); "awaiting signatory details" (Post Acute) |
| Lender signatory + authority basis | FAQ exists because it's asked repeatedly; needed for DocuSign routing slot 2 |
| Deal timeline / facility close date | Anonos and Post Acute both had hard close dates that surfaced late and created fire drills |
| Redline intent | Determines eligibility routing + Webster fee path (4/20 policy); today it surfaces only when redlines arrive |
| Lender notice address & Exhibit A bank details (optional) | Needed verbatim for agreement pages 12–13 / Exhibit A |

Also: a prospect with no Rho account can complete the whole form today (Mile High did, 3× duplicate submissions) even though the SOP requires onboarding first.

### 3.3 Redesign: two-stage, branch-aware, and never ask what Rho already knows

**Stage 1 — Qualifier (5 questions, <2 min):** Rho client? (No → route to onboarding with explanation, don't collect the rest) · single or multiple entities (multi → collect entity list) · lender legal name · expected timeline/close date · do you anticipate requesting changes to the standard template? (Yes → show redline-eligibility expectations up front).
*Outcome: every disqualified or special-path request is routed in minute one instead of week two.*

**Stage 2 — Full application (sent after Fraud initial review passes, pre-filled):** Since the requester gave their Business ID, **pre-fill entity legal name, address, EIN, registered Control Person from Salesforce/RAP and ask them to confirm, not retype** (Dynamo principle: redesign around what the system already knows). Then collect only the genuinely new facts: account choice (new clearing acct / convert existing — picker of their actual accounts) · borrower signatory (confirm CP or provide new signer → triggers KYC path) · lender signatory + authority · lender notice address · lender reps for view access (proper repeating block, fixing the duplication bug) · Exhibit A bank details (optional) · loan agreement upload · gov receivables · referral.

**Field-level requirements:** every Stage 2 field maps 1:1 to a merge field in the agreement/DocuSign envelope or a compliance-affirmation line — if a field doesn't feed one of those, it gets cut. Submission writes directly into the case register (no PDF-download-reformat-in-Word step) and the PDF for Jira/Webster is generated from the data.

**Platform note:** Typeform with branching logic + hidden fields (business_id) can do all of this today; the longer-term home is an in-app Rho flow (the "productize DACA" direction in your research doc). The two-stage structure survives either platform.

---

## 4. DocuSign: What's Possible, and the Future Agreement-Prep Design

### 4.1 Platform capabilities relevant to us (grounded in DocuSign docs)

- **Templates with named roles** ([docs](https://developers.docusign.com/docs/esign-rest-api/esign101/concepts/templates/)): the Webster-approved agreement becomes a stored template with roles (Borrower / Lender / Rho / Webster Bank) and pre-placed signing tabs — per-envelope tab dragging disappears.
- **Prefill + data tabs**: field values (dates, party names, addresses, Schedule A account number) are set **via API at send time** ([reference](https://developers.docusign.com/docs/esign-rest-api/reference/)) — the agent fills them from the case register; no Word editing.
- **Anchor (auto-place) tabs**: tabs positioned by anchor text in the document, so template revisions don't break placement.
- **Composite templates**: combine the server template with per-deal documents (e.g., attach the loan agreement or affirmation page in one envelope).
- **Recipient routing order**: the exact Borrower → Lender → Mike → Webster sequence (+ Zorica/you as CC) is encoded once in the template — unskippable, untypoable.
- **Connect webhooks** ([docs](https://developers.docusign.com/docs/esign-rest-api/reference/connect/)): push notifications on every envelope event (sent, delivered, signed-by-recipient, completed, declined, voided). This is the **canonical, real-time source for execution dates** — eliminating the date-inference failure mode the Gumloop agent had to be rule-fenced against, and replacing the email-polling auto-filing trigger.
- **Auth**: OAuth2 with **JWT impersonation grant** for service integrations acting on the account without an interactive login ([planning guide](https://www.docusign.com/blog/developers/docusign-esignature-integration-101-planning-your-integration)) — fits an agent + app backend.
- Also available if needed: embedded sending (review/adjust an API-prepared envelope in an iframe before release), bulk send, envelope custom fields (we'd stamp `case_id` on every envelope).

### 4.2 Future-state agreement prep flow (the walkthrough preview)

```
Case register (validated intake data)
   │ 1. agent assembles envelope draft from template + merge data
   ▼
PRE-SEND VERIFICATION SCREEN (human gate #1 — you)
   • side-by-side: each merge field vs its source evidence
     (entity name ←Salesforce · acct # ←RAP, confirmed deactivated if new
      · signer emails ←application, verified · routing order ←template)
   • any mismatch = hard block, not a warning
   │ 2. you approve → API creates + sends envelope (JWT service auth)
   ▼
Connect webhooks drive everything downstream automatically:
   • per-recipient progress → case register events → pinned status surface
   • stalled-signer nudges (e.g., Bud: "with borrower signer 13 days") drafted for approval
   • completed → certificate + executed PDF auto-filed to the entity Drive folder,
     completion/agreement dates written to register (canonical), Jira → Pending Final Setup,
     distribution email drafted from macro (human gate #2: approve send)
```

What this removes from your plate: Word template editing, manual tab placement, signing-order setup, completion-date bookkeeping, executed-PDF filing, and "did they sign yet?" checking. What it deliberately keeps: your approval before anything leaves Rho.

Open items to confirm before build (I'll walk you through these): which DocuSign plan features are enabled on Rho's account (Connect, document generation, embedded sending), sandbox/demo account availability for testing, and whether Webster has constraints on envelope structure.

---

## 5. Cross-cutting note

All four redesigns assume the same backbone: the **case register + append-only event log** (§1.3). The weekly Download is a query over it, the intake form writes into it, DocuSign webhooks update it, and the audit export dumps it. That's one system to keep correct instead of four artifacts to keep synchronized — which is the unit-drive redesign, not a faster steam engine.
