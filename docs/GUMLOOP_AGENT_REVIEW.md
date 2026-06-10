# Review: "DACA context" Gumloop Agent — What It Was Asked to Do, Where It Failed, and What We Carry Forward

**Date:** 2026-06-10
**Sources:** the agent's context-handoff brief (uploaded 6/10), plus directly observed behavior in #daca-ops and #daca-applications (Slack), the DACA Summary sheet, and Gmail.

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
