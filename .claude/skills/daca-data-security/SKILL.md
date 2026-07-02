---
name: daca-data-security
description: Security and data-handling architecture rules for DACA Ops. Governs how client/lender PII, account numbers, and signed agreements flow through the app — viewable on demand, not persistently stored in app-controlled storage, and never sent to Anthropic in a form beyond what a given operation strictly needs. Apply this whenever adding storage, a new integration, an LLM call, or a new document/attachment path. Also the review checklist for auditing existing code and repo contents for violations.
---

# DACA Ops — Data Security & Storage Architecture

DACA cases carry some of the most sensitive data Rho handles: SSNs and account numbers (compliance packages), signed banking agreements, signatory names/emails/titles, and lender financial details. This skill is the standing architecture rule for how that data is allowed to move through DACA Ops, and the checklist for catching violations.

**Core principle:** DACA Ops is a *view and orchestration* layer over Gmail, Jira, Drive, Zendesk, and Typeform — not a second copy of the data. The app may **display** sensitive content pulled live from those systems of record. It must not **persist** a copy of that content in its own storage (database, files, git) beyond the lifetime of the operation that needed it, and it must not send more of it to Anthropic than the specific task requires.

This is not a new idea invented for DACA Ops — it is Rho's stated position for agent-adjacent systems generally. Ground truth, in order of specificity:

1. **Rho Minion (Autonomous Coding Agent Strategy, Notion `320db9eb…`):** *"Rho is a fintech company. Agent context — code, logs, database schemas, API contracts — contains sensitive system details. Managed agents route that context through vendor infrastructure. Even with enterprise SOC 2 commitments, we have no visibility into what's retained or used in training... Our code and context stay in our infrastructure."* Same principle, different agent. The architectural answer there was: keep the sandbox and its data inside Rho's VPC, and treat what leaves the VPC (even to a trusted vendor) as the thing to minimize.
2. **AOI Enrichment System `security-design.md`** (Rhobot team, Notion `296db9eb…8184`), §7.4 Privacy by Design — the concrete pattern to copy:
   ```python
   class PrivacyPreservingEnrichment:
       def enrich_document(self, document: dict) -> dict:
           # Extract only necessary fields
           minimal_document = {
               'id': document['id'],
               'content_hash': self.hash_content(document['content']),
               'metadata': {...}  # non-sensitive fields only
           }
           # Send to enrichment service without PII
           enriched = self.call_enrichment_api(minimal_document)
           # Merge results back locally
           return {**document, 'enrichment': enriched}
   ```
   The same shape applies here: send the model what it needs to do the task (draft a reply, check a discrepancy), not the full source record, and merge the model's output back into the full record locally.
3. **AOI `security-design.md` §7.2 Data Classification** — a `DataClassification` enum (`PUBLIC` / `INTERNAL` / `CONFIDENTIAL` / `RESTRICTED`) with controls (encryption, access, retention, masking) per level. DACA case data is `CONFIDENTIAL` at minimum (signatory PII, entity financials) and `RESTRICTED` for anything account-number- or SSN-adjacent (compliance packages) — apply `RESTRICTED`-tier controls (explicit approval, audit logging, masking) to anything in that category.
4. **Claude Code Secure Usage Guide** (Rho eng wiki, Notion `31fdb9eb…`) — org-wide baseline for this harness: deny rules + hooks in `settings.json` (not `CLAUDE.md` — that's best-effort only), MCP servers reviewed and explicitly opted into per project, prompt-injection awareness when reading tool output. Applies to every DACA Ops session regardless of this skill.

**What I did not find:** an existing Rho skill scoped exactly like this one (client-PII-in-an-agent-app storage architecture). The three sources above are policy/architecture docs, not a reusable skill — this file is the first attempt at making the principle operational for DACA Ops specifically. Don't assume it's already been vetted by Security/Legal — see "Open items" at the end.

## The rule, concretely

| Data category | Example | May the app store it? | May it go to Anthropic? |
|---|---|---|---|
| Case identifiers / status | case_id, lifecycle_stage, Jira key, Zendesk ticket ID | Yes — these are references, not content | Yes, needed for routing/grounding |
| Entity/lender legal names, addresses | "Anonos Innovations LLC", business address | Only as long as the operation needs it (in-memory `CaseRecord`); not in git, not in a database row that outlives the operation | Only when the task being performed needs it (e.g. drafting a reply naming the entity) |
| Signatory PII | Name, email, title, phone | Same as above — transient, sourced fresh from Gmail/Typeform/Jira each time, never cached to disk | Same as above, minimized to what the specific draft/check needs |
| Account numbers, SSNs, compliance-package contents | Schedule A account numbers, Middesk/Alloy reports | **Never stored by the app.** Lives in RAP/Drive/compliance systems of record; the app may display a masked reference (last 4) or a status ("account confirmed") | **Never sent to the model** unless a specific, narrow task requires the literal value (e.g. filling a template field) — prefer passing a placeholder/reference and letting the human fill the literal value at review time |
| Full document bytes (signed DACAs, redlines) | .docx/.pdf content | Fetched on demand from Drive for the operation; fingerprint/hash (see `attachment_scanner.py`) may be retained for comparison — raw bytes should not be written into git or a persistent DB | Only the specific extracted facts a task needs (e.g. "does this attachment match that one" via hash comparison — not the full text) — never the raw document as unstructured context unless the task is literally "read and summarize this document" |

**"View, don't store" in this codebase today:** `CaseContextLoader.load()` (`src/context/loader.py`) already does this correctly for the read path — it fetches fresh from Gmail/Jira/Drive/Typeform into an in-memory `CaseRecord` on every call, and nothing in that module writes case content to disk. Keep new code on that same shape: build the record fresh, don't add a cache/database table that outlives the request without deliberately deciding what classification tier it needs (see table above).

## Known violation in this repo — needs your decision

`docs/prefilled_dacas/Rho_Springing_DACA_Anonos_Innovations_LLC_PREFILL.docx` and the Technologies equivalent are **committed to git** (`claude/nifty-darwin-rle1pt`, commit `03625b1`) and contain real signatory names, emails, and addresses (Joseph Sciascia, Michael Gulliford, etc.). This is exactly the pattern this skill exists to prevent — a persistent, unmasked copy of client PII living in app storage (git) rather than being generated on demand and reviewed transiently.

This needs your call, not a silent fix, because removing it cleanly means rewriting git history (a `git filter-repo`/`BFG` pass) if the branch has already been shared or pushed anywhere reviewers might have pulled it — not just deleting the file in a new commit (that leaves it recoverable from history). Options, in order of preference:
1. **Remove from git entirely, keep pre-fill outputs Drive-only** — pre-fill agents write to a scratch/temp path for human review, never commit the filled document; only the *template* (already sanitized, no client data) stays in git. Requires a history rewrite for the two files already committed.
2. **Keep committing pre-filled drafts, but redact/mask PII in the git copy** — replace names/emails/addresses with placeholders in what's committed, keep the real filled version only in Drive after DRI approval. More code, but preserves an audit trail in git without the PII.
3. **Accept the current state** if this branch/repo is already scoped as an internal, access-controlled audit trail and Legal is fine with it being in git — but that should be an explicit decision, not a default.

## What to check before shipping any new DACA Ops code

1. **New storage (DB table, file, cache)?** Classify it against the table above before adding it. If it's `CONFIDENTIAL`/`RESTRICTED`-tier content, ask: does this need to persist at all, or can it be re-fetched from the system of record each time (`CaseContextLoader`'s pattern)? Prefer re-fetch.
2. **New LLM call?** Check what's in the prompt. Apply the AOI `PrivacyPreservingEnrichment` pattern — pass only the fields the specific task needs, not the whole `CaseRecord` by default. `client_comms_agent.py` and `email_drafter.py` currently pass fairly full case context (entity names, contact names, open items) because drafting a coherent client reply genuinely needs that; account numbers and compliance-document contents are correctly never passed. When adding a new draft/analysis type, ask the same question: does *this* task need the literal sensitive value, or would a reference/placeholder do?
3. **New attachment/document path?** Follow `attachment_scanner.py`'s existing pattern — download bytes only for the duration of fingerprinting/comparison, retain the `DocumentFingerprint` (hash + metadata), not the raw bytes, once the operation completes.
4. **New integration (like the Zendesk client)?** Don't let the low-level client cache responses to disk. `ZendeskClient`/`CaseContextLoader` clients should be thin pass-throughs — the system of record stays the system of record.
5. **Anything about to be committed to git?** Grep the diff for the obvious PII shapes (emails, phone numbers, account-number-looking digit runs, SSN-shaped digit runs) before committing — the same discipline the Gumloop KB-file failure (`GUMLOOP_AGENT_REVIEW.md` Part A, failure #3) argues for generally: knowledge in git is good because it's versioned and recoverable, but that only holds if what's in git wasn't supposed to be sensitive in the first place.
6. **Skill files, CLAUDE.md, or any other file an agent reads as standing context?** Never write real client PII into these — they are exactly the kind of file that gets read into every future session's context. Reference case IDs/entity names for illustration if needed (as this repo's existing skills already do for the Anonos case), but don't add SSNs, account numbers, or full compliance-document contents even as examples.

## Open items — do not assume these are resolved

- **Rho's actual Anthropic commercial terms are not confirmed here.** The ChatGPT Enterprise Notion page documents "No data retention" as a configured feature for that vendor; no equivalent Anthropic-specific data-retention/ZDR confirmation was found in Notion during this research. Whether Rho has a Zero Data Retention agreement or specific retention configuration with Anthropic is a question for IT/Legal/the Anthropic account team, not something to assume from the ChatGPT precedent. Until confirmed, treat "minimize what's sent" (this skill) as the control that doesn't depend on the answer.
- **No case register/database exists yet** (`REDESIGN_PROPOSALS.md` §1.3 proposes one). When it's built, its schema needs the classification tiers from this skill applied column-by-column before any DACA data lands in it — this skill should be revisited at that point, not treated as fully satisfied by today's in-memory-only pattern.
- **Legal/Security have not reviewed this skill.** It's grounded in real internal precedent (Rho Minion, AOI security-design.md) but was written by an agent, not vetted by Rho's Security or Legal teams. Treat it as a strong starting draft for DACA Ops specifically, not an approved company policy.
