# Rho DACA Operations — Current State Assessment

**Date:** 2026-06-10
**Compiled by:** DACA Ops agent (Claude Code), from a direct review of Jira, Gmail (daca@rho.co), Notion, Slack, and Google Drive.
**Status:** Foundation document for the DACA Ops tool build. Every claim below is sourced; items marked ⚠️ are partial or unverified.

---

## 1. Program Overview

A DACA (Deposit Account Control Agreement) at Rho is a **four-party agreement** between Rho (Platform — Under Technologies Inc. dba Rho Technologies), **Webster Bank N.A.** (Bank), the Client/Borrower, and the Lender (Secured Party).

**Hard constraints (per Notion SOP "Rho DACA Process", updated 2026-05-27):**
- **Springing DACAs only** — no fully-blocked products.
- **Checking accounts only** — no Treasury / Prime Treasury.
- Webster can decline account opening or request offboarding at any time.
- Rho does not intend to collect DACA fees (despite fee schedule in agreement).
- Terminology rule: always "DACA request application," never "survey"/"questionnaire."
- Turnaround: 1–2 weeks after all parties sign; Webster countersign 2–5 business days.

**People (DRI table from SOP):**
| Role | Primary | Backup |
|---|---|---|
| DACA program ownership / DRI | Shani Abrahams | Mike Szarowicz (CFO, also Rho signatory) |
| Intake (daca@rho.co), client/lender comms, Jira, agreement admin, Webster relationship | Shani Abrahams | CS team (Zorica Tasic) |
| Initial fraud review | Fraud team (Nebojsa Satava for Unit 21/TM) | — |
| Compliance package assembly | Vladan Novkovic (OOO until ~Jun 21; sub: Josh Bobowski) | Jeff Pasquerella |
| Legal questions & redlines | Sam Davidson (separate Legal board ticket, linked) | — |

**Webster contacts:** webster_rho_daca@websterbank.com (group box); Sttefany Oliveira (stoliveira — primary approver + monthly report recipient); Sarah Hickey (shickey); Kevin Jamison (kjamison); Melissa Santos (mesantos — DocuSign signatory, Exec. Managing Director); Jenifer Troy (jtroy — Webster Legal, redlines). Redlines are exchanged via **Webster's ShareFile folder**.

---

## 2. Documented Process Flows (sources of truth)

### 2.1 Primary SOP — Notion "Rho DACA Process" (page `245db9eb…`, updated 2026-05-27)
Six phases, with Jira statuses (flow implemented 11/26 on the CS Helpdesk board, issue type **"DACA Request"**):

1. **Intake** — inquiry arrives (Sales/Partnerships/CS → cc daca@rho.co) → send DACA request application (Typeform) → DRI creates Jira ticket + updates DACA Summary Sheet → status **Fraud Initial Review**.
2. **Data collection** — Fraud approves → send template macro → **Typeform Sent**; redlines → **Legal Redline Review** (separate Legal ticket; redlines discouraged, allowed for VIP/high-value/churn-risk per redlining-eligibility criteria page).
3. **Compliance package** — Typeform PDF attached to Jira, tag Compliance → **Pending Compliance Package Assembly**. Checklist: DACA request application PDF, agreement copies, compliance approval, Middesk report, address verification (vs RAP + agreement), EIN/TIN match, Alloy good-standing, signatory/UBO reports, AOI, name-change/DivCorp filings as applicable. Then **DRI pre-Webster package review gate** before submission.
4. **DocuSign** — signing order strictly: Borrower → Lender → Mike Szarowicz (Rho) → Webster (Melissa Santos); Exhibit A optional for lender → **Docusign Sent**.
5. **Account setup** — new account path: create clearing account in RAP, grab account number immediately (Schedule A), deactivate until execution, reactivate after; existing-account path: ENG ticket to convert deposit → clearing account (examples: ENG-35904, ENG-37779) → **Pending Final Setup** → upload executed agreement to DACA Drive, complete Salesforce DACA fields, distribute agreement → **Done**.
6. **Ongoing** — weekly status updates on in-progress DACAs; monthly Active/In-Progress DACA list to Sttef Oliveira (Webster); Slack channels `#daca-applications` (new/in-progress) and `#daca-transactions` (post-setup monitoring). Currently observed channel in use: **#daca-ops** with Gumloop bot feeds.

### 2.2 Trigger Event Playbook — Notion (page `36ddb9eb…806e`, updated 2026-06-01) **← newest policy**
- **TLDR change:** moving away from pre-converting accounts to clearing accounts by default. Single-account: convert only at trigger. Multi-account: skip RAP entirely (deactivate + Unit 21 Fraud rules `RHO044_DACA_ACCOUNTS_REALTIME`).
- **Root cause:** RAP product constraint — **one clearing account per entity**; Block Account can't span multiple accounts. Pre-conversion creates friction for long-tenured clients.
- Trigger SLA: **2-hour verification** (business hours 8am–5pm) of lender identity vs Salesforce + signed agreement; urgent Jira to Compliance (cc FinOps/Legal/CS); Block Account in RAP (single) or immediate deactivation + Fraud rules (multi); notify **lender only** — Rho does not notify borrowers.
- Post-trigger: borrower view-only on DACA account (other accounts unaffected); lender controls via DACA Investor role; auto-sweep needs Banking ticket (Stevan Milic) + daily cadence/amount 0; multi-account money movement is fully manual.
- **Open questions (named owners):** multi-account Block Account support (Rishi); account-level vs entity-level borrower permission removal (Rishi); custom sweep cadence (Rishi); whether role reversal is legally required vs deactivation+monitoring sufficient (Sam); Daily Terms card block during transition (Rishi). Webster multi-account exceptions: workable, reference ICAT precedent.
- ⚠️ Multi-account exposure window between deactivation and Fraud rules going live — speed-critical.

### 2.3 Termination Process — Notion (page `36ddb9eb…8025`, updated 2026-05-27)
- **1-business-day SLA** to verify lender termination request (email vs Salesforce + agreement; else phone/written authorization) → Legal Help ticket for confirmation → confirmation email.
- **Scenario 1 (not blocked):** lower risk; Fraud removes Unit 21 "DACA" tag; update DACA Summary (Status `Terminated` + date); file in "Termination Agreements" subfolder; account stays open as regular operating account.
- **Scenario 2 (blocked):** higher risk (social-engineering motive); confirm in writing whether termination pairs with final Disposition Instruction / release of funds / silence; **coordinate funds disposition before terminating**; hold Unit 21 tag until remittance complete.
- Open question to Legal documented in-page: who may terminate (lender: yes; Rho/Webster: unanswered; client: only jointly with Secured Party).
- Known failure: **no internal notification when Championship Transportation's DACA account closed** (noted in SOP as a gap to build into the flow). Champion Transportation DACA terminated 5/15/26.

### 2.4 Supporting assets
- DACA request application: Typeform `f5xT4WRX` (+ Gumloop "DACA TypeForm Processor" → Slack + Google Sheet).
- DACA Summary Tracking Sheet (Google Sheets `140z-O_Zo…`).
- DACA Google Drive folders (intake docs `1C3Auc6…`; executed agreements `121c4-xo…`).
- SendSafely dropzone for document upload.
- Salesforce DACA fields for record-keeping; RAP (Rho Admin Platform) for account actions; TCT for account/routing lookup; Unit 21 for TM tags/rules; DocuSign via contracts@docusign.rho.co.
- Custom/legacy DACA setups (separate page): Axis Global Systems, ICAT Logistics, G&B Packing, Champion Transportation (terminated 5/15/26). Rho-as-lender cases exist (e.g., CIM 15-I LLC <> Rho Origination CA Inc., CSHELP-7735; Flax Labs Typeform with Rho Originations CA as lender; "Rho DACA w/Runway" covered-collateral sheet for Under Technologies / RBB Treasury / Rho Origination — Rho-side DACAs with Runway Growth as lender are being spun up via the normal customer process per Mike Szarowicz, 6/5).
- Older/outdated docs exist and should be superseded carefully: "DACA Set Up Process OUTDATED" (Notion), "DACA Playbook" (Notion, 2025), DACA Operations Manual versions in Drive (v3.1 2024, Webster Review 2023, Final (RAP) 2025-10, Final (U21) 2026-01, "Operations Manual 2.0" Google Doc 2026-01).

---

## 3. Live Pipeline Snapshot (2026-06-10)

From Jira (`text ~ "DACA"`, CSHELP/ENG/COMPLHELP/FRAUDTM/FOPS/UWH boards), Gmail page 1 (~30 of ~201 threads), and #daca-ops Slack:

| Case | Stage | Notes |
|---|---|---|
| **FINALIS (1053)** | CSHELP-8739 Fraud Initial Review (multi-entity) | Fraud review requested via #f-cs_fraud 6/10; lender asking for §6(b) reimbursement-language change (Mariano Riccio, 6/9); related test ticket CSHELP-8738 rejected |
| **Anonos Innovations / Technologies** | Legal redline with Webster | "TIMELY" — client closing deadline; revisions submitted 6/1; Sam Davidson uploaded redlines to ShareFile 6/8, follow-up 6/9 asking for next-morning response; client pressing for 6/10 answer; ad-hoc "anonos-daca-response-monitor" Drive folder created 6/10. A separate earlier Anonos redline was approved by Webster Legal for remaining entities (Assist ticket closed 6/10) |
| **Bud Financial (46826)** | CSHELP-8139 Docusign Sent | DocuSign out 5/28, awaiting Ed Maslaveckas (first signer); client followed up 6/10; agreement re-sent. UBO review COMPLHELP-2536 in "CS: Follow Up With Client" |
| **Post Acute Analytics (1911)** | CSHELP-8539 Docusign Sent → executed 5/26 | Lender: Customers Bank (Luke Bulino). Signed PDF in Drive; compliance package approved by Webster 5/26 |
| **Apomaya dba Lokker (47115)** | CSHELP-7653 Templates/Agreement Sent (since 3/26) | ⚠️ stale — no movement visible in ~2.5 months |
| **Edwards Holdings (6 entities)** | CSHELP-6720 Docusign Sent; ENG-39710–39714 conversions (4 Done, Edwards Moving In Progress) | DACA designation switch 7305→9972 with ENG; client (Lindsey Robinson) also requesting duplicate-account closures + account nicknames; earlier fallout: admin lost visibility, card declines |
| **Runway Growth (Rho-side DACAs)** | New — kicked off 6/5 | 3 Rho entities to cover via normal customer process; template sent to Cody Jones (Runway) + Sidley 6/5 for approval |
| **Mile High Energy Solutions** | Application received 5/6 | Lender 1st Commercial Credit; borrower has **no Rho account yet** (must onboard first); 3 duplicate Typeform submissions |
| **Canvas Medical** | Done (CSHELP-7485, ENG-38083) | Post-setup issues: unexpected auto-sweep into DACA; insufficient checking balance for credit repayment (CSHELP-8656) |
| **ICAT / PineBridge** | Terminated 5/15 | Parallel termination notices from Moore & Van Allen and Webster ("URGENT"); ICAT was the multi-account precedent |
| **Champion Transportation** | Terminated 5/15/26 | FRAUDTM-2609 DACA tag removal Done; closure happened without internal notification (documented gap) |

Recurring obligations: **Monthly Rho<>Webster DACAs list** to Sttef (Mar/Apr/May sent; May noted a termination exclusion manually); weekly in-progress status updates.

---

## 4. Systems & Tooling Landscape

One DACA case currently touches: **Gmail (daca@rho.co) → Typeform → Gumloop (2 bots: "DACA context" email mirror + "DACA TypeForm Processor") → Slack (#daca-ops, #f-cs_fraud, #transactionmonitoring) → Jira (CSHELP "DACA Request" type; ENG conversions; COMPLHELP; FRAUDTM; Legal board; FOPS) → Google Drive (intake + executed agreements) → DACA Summary Google Sheet → DocuSign → RAP / TCT / Unit 21 → Salesforce → ShareFile (Webster's, for redlines) → SendSafely**.

There is **no single source of truth for case state**. State is inferred from Jira status + mailbox memory + the tracking sheet, each updated manually.

### Existing automation (Gumloop) — observed behavior in #daca-ops
- Mirrors each daca@ email into Slack with sender/subject/snippet. Formatting is inconsistent message-to-message; many notifications carry no analysis (raw rebroadcast).
- **Defects observed:** duplicate notifications (3 identical posts for Mile High on 5/6 — user called it out in-channel; bot acknowledged "3 identical submissions detected"); answering "what are the outstanding daca emails" and "summarize the Anonos situation" requires manual prompting.
- Typeform processor posts application summaries + writes to a Google Sheet.

---

## 5. Pain Points (evidence-based)

1. **Pipeline visibility gap.** Shani's own research doc (Jan 2026): *"at any given time/date, need immediate visibility into where a daca is in the process"*; *"Webster very frustrated on current process, fix this asap!"* (communication issues dating to 2023). Corroborated by: stale Lokker ticket (Templates Sent since 3/26), Intelligo transfer error sitting ~6 days, clients chasing (Edwards CFO: "We need to get this finalized ASAP").
2. **Redline lane is the bottleneck + highest pressure.** Anonos timeline: 6/1 submission → 6/3 apology for late acknowledgment → 6/8 ShareFile upload → 6/9–6/10 client deadline pressure. Process spans Rho Legal, Webster Legal, ShareFile, email — no shared status.
3. **Manual, duplicative record-keeping.** Drive: triplicate Notion exports, ".eml dump" folder with (1)/(2)/(3) re-downloads, template PDF with trailing-space filename, key docs scattered across roots/folders; tracking sheet and Salesforce updated by hand; monthly Webster report assembled manually (termination exclusions handled by memory).
4. **Repeated FAQ answering.** "Springing only / checking only / no fully-blocked" individually restated to Nirvana, Bud, Bison, Anonos, Post Acute Analytics. Unqualified leads enter the funnel (Mile High has no Rho account; Bison wanted blocked DACAs).
5. **Notification noise + bot distrust.** Duplicate Gumloop posts, "follower" notification clutter in the mailbox, degraded subject lines ("[Rho] Re: Re: [Rho] Re: Re:…").
6. **Cross-team handoffs are invisible.** Fraud/Compliance/Legal/ENG steps live on different boards with different status vocabularies; the SOP's own example: no notice when Championship Transportation's account closed. Coverage risk during OOO (Vladan → Josh sub arranged via DM).
7. **Product constraints generate ops workarounds.** One-clearing-account-per-entity (RAP); entity-level (not account-level) permissions; no custom sweep cadence; Daily Terms card can't be blocked during transition; DACA missing from "Transfer to" dropdown for some businesses (ENG-38833, Backlog); transfer failures Primary→DACA (ENG-39026).
8. **Trigger/termination are safety-critical with tight SLAs** (2h / 1d) and known exposure windows (multi-account deactivation → Unit 21 live), plus social-engineering risk on terminations (Scenario 2).

---

## 6. Coverage Notes (what this assessment did and did not see)

- Jira: full JQL sweep of "DACA" text matches (top ~50 reviewed in detail across CSHELP/ENG/COMPLHELP/FRAUDTM/FOPS/UWH/KYC).
- Gmail: **page 1 of ~201 threads** (2026-04-07 → 06-10) analyzed in depth. ⚠️ Remaining ~170 threads unreviewed; no trigger-event (Initial Instruction) emails appeared in the reviewed window.
- Drive: **first 25 results** analyzed. ⚠️ More files behind pagination, incl. the main executed-agreements folder.
- Notion: main SOP + trigger playbook + termination page fetched in full. ⚠️ Not yet fetched: DACA Criteria Overview, Redlining Eligibility Criteria page, custom-DACA-setup page.
- Slack: #daca-ops recent history + global search. ⚠️ #daca-applications / #daca-transactions (named in SOP) not yet located — current activity is in #daca-ops.
- Salesforce, Snowflake, Hex, Help Center: not yet queried.

---

## 7. Design Implications for the DACA Ops Tool (per user-supplied references)

Grounded in: Anthropic *Building Effective Agents* + Claude Code best practices; **"Code as Agent Harness"** (arXiv:2605.18747); **Paul David, "The Dynamo and the Computer"** (AER 1990).

1. **Unit-drive, not group-drive (David):** don't re-broadcast emails (the current Gumloop pattern). Redesign around a **DACA Case** as the unit of work — one stateful record per case carrying stage, SLA clocks, evidence links, blockers, and next action, synthesized from Gmail/Jira/Drive/Salesforce.
2. **Harness over model (Code as Agent Harness):** agent outputs are produced through executable, verifiable steps — checklists evaluated against actual documents, drafts generated from approved macros with source citations, state transitions validated against the SOP's allowed flow. Execution traces = memory; verifier checks before anything reaches the human.
3. **Workflows over open-ended agents (Anthropic):** DACA work is classifiable (new request / redline / compliance package / DocuSign chase / trigger / termination / reporting / account ops). Route to per-type structured workflows; reserve agentic behavior for genuinely novel inquiries.
4. **Human as verifier, with hard gates** at: pre-Webster package submission, any outbound external email, trigger-event execution, termination confirmation — mirroring the SOP's existing review gates and the paper's "human oversight for safety-critical actions."
5. **Show evidence, not assertions:** every drafted reply/checklist item links its source (email, agreement clause, Middesk/Alloy report, Jira comment) so verification is a glance, not an investigation.
6. **Fix the two loudest current failures first:** dedupe/idempotency in notifications, and an always-current pipeline board answering "where is every DACA right now?" — the exact question the DRI currently asks the bot manually.
