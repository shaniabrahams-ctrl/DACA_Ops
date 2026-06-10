# Review: DACA Gumloop Agents — What They Were Asked to Do, Where They Failed, and What We Carry Forward

**Date:** 2026-06-10
**Sources:** the "DACA context" agent handoff brief, the "DACA Monthly Reporter" context summary, and the "DACA TypeForm Processor" agent summary (all uploaded 6/10), plus directly observed behavior in #daca-ops and #daca-applications (Slack), the DACA Summary sheet, and Gmail.

This review covers three agents: **Part A — "DACA context"** (general-purpose assistant), **Part B — "DACA Monthly Reporter"** (monthly Webster report), **Part C — "DACA TypeForm Processor"** (intake alerts), and closes with a **cross-agent synthesis (Part D)**.

---

# Part A — "DACA context" agent

---

## 1. The mandate it was given

Nine recurring task types: (1) answer DACA inquiries from a knowledge base, (2) draft intake/first replies in Shani's voice, (3) auto-file completed DocuSign agreements to Drive, (4) new-DACA-email alerts to #daca-ops, (5) client status-change alerts, (6) draft the weekly "Download" (Fri 10am → DM for approval), (7) daily Notion→knowledge-base sync, (8) create CSHELP Jira tickets + add tracker rows after template issuance, (9) maintain tracker notes/statuses/dates.

This is a sensible mandate. The failures below are mostly **architecture** failures, not mandate failures — worth being precise about, because the same mandate carries into the new tool.

## 2. Documented + observed failures, with root causes

| # | Failure | Evidence | Root cause |
|---|---|---|---|
| 1 | **Fabricated/inferred dates** — treated email send dates and Jira timestamps as execution dates | Handoff §9.1; the elaborate §2.2 canonical-source rule exists *because* this happened | Free-text reasoning over proxies; no structured source for dates (fixed properly by DocuSign webhooks → register, see REDESIGN_PROPOSALS §4) |
| 2 | **Duplicate notifications** — 3 identical "New DACA Application" posts for Mile High (5/6); you called it out in-channel | #daca-ops history | No idempotency: nothing deduplicates on (form_response_id); each trigger fire posts blindly |
| 3 | **Knowledge-base destroyed by an unrelated automation** (5/20) — an unrelated trigger overwrote `daca_knowledge_base.md`; 46 historical tickets, case precedents, template/personnel directory **still unrecovered** | Handoff §9.6, §11 | Mutable single-file memory with no versioning, no access isolation, no backup. (Our build: knowledge lives in **git** — versioned, diffable, recoverable by construction) |
| 4 | **Fired actions whose completion is unknown** — the 6/5 FINALIS template send + ticket/row creation was queued and the handoff itself says "verify it actually completed" | Handoff §11 | No execution receipts / run ledger; the agent's word is the only record (the harness paper's core point: execution logs must be the memory) |
| 5 | **Alert false positives** — the "3 - DACA" Gmail label catches outbound mail (incl. the monthly Webster report) and re-labeled old mail re-fired triggers | Handoff §9.4–9.5; the 3-day freshness gate is a patch | Classification done per-event by LLM judgment over a noisy stream, instead of deterministic filters (direction, sender domain, message-id dedupe) in code with LLM only for the residual |
| 6 | **Jira over-advancement risk on a forward-only workflow it cannot undo** — and no delete permission to recover from mis-creates | Handoff §3.5, §9.3 | Side-effectful actions without a dry-run/confirm step on an irreversible system |
| 7 | **Tracker note bloat** | Handoff §9.7 (and visible in the Note column today) | The sheet was the only home for narrative; with an event log, notes become one-phrase by design |
| 8 | **Slack posts that render empty in search/exports** | Multiple #daca-ops Gumloop messages with blank text in search results | Block-Kit-only payloads with no text fallback — breaks search, accessibility, and any downstream tooling |
| 9 | **Inconsistent message formats across runs** | Compare the three Typeform alert formats in #daca-ops (5/6 vs 5/22 vs 5/26) | Format lives in the prompt, re-improvised per run, instead of one code-rendered template |
| 10 | **Config drift/ambiguity** — #daca-tracking and #daca-applications recorded as the same channel ID; weekly cadence silently lapsed after 5/22 | Handoff §11; channel history | No validated config; no failure alarm when a scheduled deliverable doesn't ship |

## 3. What it got right (keep these)

The behavioral rules are genuinely good and hard-won — they encode your corrections:

1. **Anti-fabrication with canonical-source priority order** for dates/values; blank-and-flag over invent.
2. **Surface drafts in chat first; never auto-send/auto-draft externally** without explicit instruction.
3. **Retrieve/compute before asking** — only escalate for missing sources, judgment calls, or irreversible/external actions.
4. **Voice + language discipline** ("DACA request application", signature style, subject-line conventions, never inventing tier labels).
5. **Human gate on the weekly post** (draft → DM → approve).
6. **JQL discipline** (tracker first, `ORDER BY created DESC`, entity-scoped searches).

**The difference in the new build: these survive as enforced properties, not prompt requests.** A rule that lives only in a prompt degrades under context pressure (we saw exactly this across the failure list). The same rule as a harness property cannot:

| Prompt rule (Gumloop) | Harness property (new build) |
|---|---|
| "Never infer dates from proxies" | Dates only enter the register via typed sources (webhook payload, certificate parse, sheet cell); free-text dates are rejected at write time |
| "Don't post duplicates" | Idempotency keys on every outbound action (message, ticket, row) |
| "Verify the send completed" | Every action returns a receipt into the append-only event log; a reconciler flags actions without receipts |
| "Don't overwrite the KB" | Knowledge in git, write-scoped per workflow, PR-style diffs for SOP changes |
| "Forward-only Jira, don't over-advance" | Allowed-transition map in code; out-of-order transition is unrepresentable |
| "Post weekly on Fridays" | Scheduler + dead-man switch: missed deliverable pages the human instead of silently skipping |

## 4. Disposition recommendation

Keep the Gumloop agent running untouched while we build (it's load-bearing for alerts and the weekly draft). Migrate workflow-by-workflow onto the case register, retiring each trigger only after its replacement has run in shadow mode for at least one full cycle with receipts verified. Highest-value first: (1) status/pipeline surface, (2) weekly Download generation, (3) DocuSign webhook ingestion, (4) intake. Also: re-import the lost KB content (46 historical tickets, precedents) **into git** as part of step 1 so the loss event can't recur.

---

# Part B — "DACA Monthly Reporter" agent

## B1. The mandate

Monthly (1st @ 9:00 AM ET, for the previous month-end): read the `2026` tracker tab → filter to Active/Blocked/In progress → renumber sequentially → generate PDF + Excel ("Rho<>Webster DACAs List - YYYY-MM-DD") → rewrite the `WebsterReport` tab → archive both files to a monthly Drive subfolder → create a Gmail draft to Sttef/Sarah/Kevin (cc daca@rho.co) for Shani to review and send.

## B2. What it gets right

This is the best-designed of the two agents, and its spec quality shows what "workflow over open-ended agent" buys:

1. **Draft-only delivery** — Shani reviews and sends; the human gate is structural.
2. **Permanent Drive archive per month** — an actual sent-artifact audit trail.
3. **Deterministic written rules** (filter set, renumbering, file naming, formats) instead of per-run improvisation.
4. **Renumber-after-filter rule** correctly anticipates a real error class (sheet `#` gaps leaking into the report).

## B3. Defects and risks

| # | Issue | Detail |
|---|---|---|
| 1 | **Inherits every tracker defect (GIGO)** | The report is a projection of the 2026 tab — which has duplicate rows, stale statuses, and missing dates (REDESIGN_PROPOSALS §1.2). Example: if the duplicate POST ACUTE rows were both in an included status, Webster would receive a double-counted list. There is no dedupe-by-Business-ID and no anomaly check before send. |
| 2 | **Incomplete status filter spec** | The filter table enumerates only 5 statuses, but the sheet actually contains at least 7 (also "Fraud Initial Review", "TERMINATED", "Rejected"). Unlisted statuses fall through to *implicit* behavior. The May termination was excluded by Shani's manual judgment, not by a written rule — exactly the kind of silent dependency on one person's memory this process shouldn't have. |
| 3 | **Email body vs. content mismatch** | Body says "Active and In-progress" but the report includes **Blocked** (triggered) DACAs too — a partner-bank-facing wording inaccuracy waiting for a question from Webster. |
| 4 | **Hardcoded clear range `A1:E60`** | At 44 rows and growing, once the list passes ~57 entries, stale rows below row 60 would survive a rewrite. Silent truncation/corruption mode. |
| 5 | **No month-end cutoff logic** | Runs on the 1st against *current* sheet state. A DACA executed May 31 but recorded June 2 is missing from the May report; one completed June 1 at 8am would wrongly appear. No as-of-date filtering on event data. |
| 6 | **No receipts, no dead-man switch** | Nothing verifies the draft was created, that attachment row counts match the filtered query, or — critically — that the draft was ever **sent**. If the DRI is OOO on the 1st (Vladan's OOO this month shows how real this is), the report silently doesn't go out. |
| 7 | **Continuity hardcoded to one person** | Signature, sender, and reviewer are all Shani by name (including a job title the other agent's style rules prohibit). No backup path from the DRI table; the user's stated goal — continuity through org changes — is unmet by design. |
| 8 | **Fragile plumbing** | The 4-hop clean-filename workaround (sandbox → storage → Drive → download-back → draft) exists to patch a platform limitation; each hop is an unverified failure point. |
| 9 | **Cross-agent interference** | The other agent's email-alert classifier had to be special-cased to *not* alert on this agent's own outbound report — two agents working around each other with no shared state. |
| 10 | **Snapshot-only content** | Sttef must manually diff against last month to see what's new/completed/terminated. The single most useful piece of information — the delta — is absent. |

## B4. Future state (register-backed, same human gate)

The monthly report becomes a **generated view over the case register** (REDESIGN_PROPOSALS §1.3):

- **Inclusion by rule over a closed enum** — every lifecycle/control state is explicitly mapped in/out; a new status cannot silently fall through. Dedupe by case ID is structural.
- **As-of-date correctness** — the report is computed from the event log *as of month-end*, so late-recorded events land in the right month, and a regenerated report for any past month is reproducible (audit requirement).
- **Delta section** — "Changes since last report: +2 executed (names, dates), 1 terminated (name, date, secured party)" — generated from events between the two report dates.
- **Verifier separate from generator** — a manifest (row count, included IDs, content hash) is recomputed independently from the register and must match the artifacts before the draft is created; mismatch blocks and pages.
- **Receipts + dead-man switch** — draft creation, archive upload, and the human send are all logged events; unsent by the 3rd → reminder to the DRI; unsent by the 5th → escalate to the backup from the DRI table. Sender identity, signature, and backups come from config, not hardcoded prose — **continuity survives personnel changes because the process is code + config in git, not knowledge in someone's head**.
- Body copy fixed to match content ("Active and In-Progress DACAs, including any currently under lender control") — pending your wording preference.

Priority-wise this stays behind the pipeline surface and weekly Download (per Part A §4), but it's the cheapest full demonstration of the register→view→verify→human-gate pattern, and a strong candidate for the first end-to-end workflow we ship.

---

# Part C — "DACA TypeForm Processor" agent

## C1. The mandate

Poll the Typeform-fed Google Sheet (`1Oog92OT…`, tab "DACA Application Form") every 5 minutes; on a new non-test row, post a structured alert to #daca-ops (lender, rep, borrower, contacts, has-Rho-account flag). Informational only — no ticket, no tracker row, no routing.

## C2. Defects

| # | Issue | Detail |
|---|---|---|
| 1 | **Its own spec admits the headline bug is unfixed** | §10: "Trigger fires multiple times for the same submission — Known/unresolved" and "Duplicate detection logic not yet implemented — Open," while §5 says dedupe "MUST be applied every time." The rule exists as prose; the trigger doesn't implement it. This produced the 5/6 Mile High triple-post (rows 77–80 are still duplicated *in the data*, not just the alerts) — the single clearest example of a prompt rule that needed to be a harness property. |
| 2 | **Wrong dedupe key even as specified** | "Same lender+borrower combo in the last few rows" is a heuristic. Typeform assigns every response a unique token — the correct idempotency key. The heuristic both under-catches (dupes beyond "the last few rows") and over-catches (a legitimate corrected resubmission from the same lender/borrower would be silently suppressed). |
| 3 | **Polling a sheet instead of consuming the form's webhook** | Typeform webhooks deliver each response exactly once with the response token. Polling row-diffs every 5 minutes is the architecture that *creates* the duplicate problem. |
| 4 | **~60% of the production sheet is test noise** | 80 rows, ~32 real. Test data lives in the production intake sheet, handled by string-matching `"test"/"Test"` on the lender-name column (misses "TEST", "testing", etc.). Blank lender name → row silently skipped, but a real submission missing its lender name is a data-quality *alert*, not a skip. |
| 5 | **Hardcoded 0-indexed column map** | Columns 0–25, including the duplicated rep blocks (6–11) inherited from the form's branching bug. Any Typeform edit silently shifts the mapping — alerts would post wrong data with full confidence. |
| 6 | **Stale persistent memory, demonstrably** | Same mutable-file memory pattern as Part A (`context.md`, "restored across ALL conversations"). Its "current data state" says the latest real submission is Mile High (5/6) — but Post Acute Analytics submitted via Typeform on 5/22 (posted in #daca-ops by this very agent). The memory file is already wrong about the thing it exists to remember. |
| 7 | **Alert format drift** | The spec's format (§8) matches none of the three observed alert formats in #daca-ops (5/6 vs 5/22 vs 5/26 differ in fields, emoji, and layout). Spec and behavior have diverged in both directions. |
| 8 | **Dead-ends the workflow** | The alert carries the qualifier signal (Has Rho Account: No → should route to onboarding per SOP) but triggers nothing: no Jira ticket, no tracker row, no case linkage. A human must re-key everything — and ticket/row creation is a *different agent's* job (Part A §6.8), with no shared state between them. |

## C3. What it got right
The alert content selection is good (lender/borrower/contacts/Rho-account flag is exactly the triage information), test-row filtering is the right instinct, and channel discipline is explicit. The structured summary doc itself is well-organized — the *specs* of all three agents are consistently better than their *enforcement*.

---

# Part D — Cross-agent synthesis (all three)

Looking across the three agents, the individual bugs are symptoms of four shared architectural decisions:

1. **No shared state.** Three agents, three private memories (a KB markdown file, a `context.md`, prompt-embedded specs), all secondary to a spreadsheet none of them owns. The duplicate Slack alerts, duplicate Drive folders, duplicate sheet rows, and duplicate tracker rows are all the same missing primitive: **an idempotent shared case register**.
2. **Rules live in prose, enforcement lives nowhere.** Every agent has thoughtful MUST-rules born from real incidents — and every observed failure violates one of its own written rules. Prompt text does not execute; harness code does.
3. **Events are inferred, not consumed.** Polling sheets and re-classifying labeled email reconstructs events that the source systems (Typeform webhooks, DocuSign Connect, Jira webhooks) will simply *deliver*, exactly once, with stable IDs.
4. **Agents interact only by colliding.** Part A's classifier special-cases Part B's outbound mail; Part C alerts on submissions that Part A separately processes into tickets; nobody reconciles. In the target design these are workflows over one register, so "coordination" is just reading the same state.

**Intake future state (replaces Part C entirely):** Typeform webhook → register `intake` event keyed on response token (idempotent by construction) → validation (schema + business rules: Rho account exists, entity matches Salesforce, no open case for same entity+lender) → one Slack alert from a code-rendered template + an auto-drafted Jira ticket and case record for DRI approval → unqualified submissions auto-routed (no Rho account → onboarding path) with a drafted reply. Test submissions go to a separate sandbox form, never into production data.
