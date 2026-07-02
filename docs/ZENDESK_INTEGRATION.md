# Zendesk Integration — Client-Facing Comms Channel

**Date:** 2026-07-02 · **Status:** Built (`src/integrations/zendesk_client.py`, `src/agents/client_comms_agent.py`), not yet run against a live Zendesk account. Env vars (`ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN`) not yet configured for this repo.
**Reference:** Rho's "Signal" tool's Zendesk integration (fraud/TM), reviewed 2026-07-02 and used as a design guide — not copied in.

## Why this exists, and what it is not

DACA_Ops has two comms surfaces that do different jobs and must not be conflated:

| Channel | Purpose | Owner module |
|---|---|---|
| **Jira/CSHELP** | Internal, end-to-end case tracking: intake → fraud review → compliance package → DocuSign → account setup. Never client-facing. | `src/context/loader.py`, `src/operations/registry_syncer.py` (existing) |
| **Zendesk + Gmail** | Client-facing conversation: the client writes in, Rho replies, attaches documents, shares SendSafely links for sensitive uploads. | `src/integrations/zendesk_client.py`, `src/agents/client_comms_agent.py` (new) |

A case's `CaseRecord` can now carry both a Jira ticket (internal) and one or more `ZendeskTicket`s (client-facing) — see `src/context/record.py`. They are separate lists; a case investigation should never assume one implies the other.

## What was borrowed from Signal, and why it was right

1. **Auth header built once from env vars, reused across requests** — `email/token:api_token`, Basic-encoded. The `/token:` separator is not optional; omitting it produces a silent 401, not an error that points at the cause.
2. **Search API for ticket lookup, not a dedicated org endpoint** — those often need admin scope a service account may not have. `find_ticket_for_client()` tries requester email first (more precise), falls back to entity name, and never raises on a miss — a case can legitimately have no Zendesk ticket yet.
3. **Parallel ticket + comment fetch** — `get_ticket_with_thread()` uses `asyncio.gather`, matching the pattern already used throughout `CaseContextLoader`. If the comment fetch fails, the ticket still returns with an empty thread rather than blocking the whole case investigation on a partial outage.
4. **Macros surfaced as reply-template candidates.**
5. **Two-tier connection test** (read check, then a tagged write check) to verify credentials before ever touching a real case.

## What's different here, and why

1. **Hard human-approval gate on every send.** This is a repo-wide rule, not new to Zendesk — `docusign_preparer.py` produces manifests but never calls DocuSign; `email_drafter.py` returns drafts but never calls Gmail's send. `zendesk_client.py` follows the same shape: `post_comment()` and `create_ticket()` both require a non-empty `approved_by` argument and raise if it's missing, so the human identity is enforced by the function signature, not by a comment saying "don't call this without review." `client_comms_agent.py` is the only module that should ever call these — `generate_reply()` drafts, `send_reply()` sends, and nothing in between calls itself.
2. **Zendesk here is a live, shared, client-facing queue.** Signal's write-check (create a tagged ticket, glance at it in the agent view) is fine for an internal fraud-tooling instance. In DACA's Zendesk, real clients file tickets in the same queue. `test_write()` creates the connection-check ticket with only an **internal-only comment** (`public=False`) — Zendesk tickets are internal-visibility by default until a public comment is added, so a stray test run can never become client-visible. Close it after eyeballing it; don't let connection checks accumulate in a queue clients also use.
3. **Attachments and SendSafely are first-class**, since sending documents and requesting sensitive ones back is the explicit reason this channel exists for DACA Ops (per your description: templates out, compliance docs back). `upload_attachment()` implements Zendesk's two-step upload-token flow for direct attachments; `build_sendsafely_block()` embeds the standard dropzone link (`https://rho.sendsafely.com/dropzone/daca`, from the SOP) for anything that shouldn't go through email/Zendesk as a raw attachment — SSNs, account numbers, IDs.
4. **Macros are cross-referenced, not authoritative.** The git-versioned macros in `email_drafter.py` (sourced from the Notion SOP) are what `generate_reply()` grounds its style guide on. `list_macros()` pulls Zendesk's copies for parity-checking, not as a content source — this is a direct lesson from `GUMLOOP_AGENT_REVIEW.md` Part A, failure #3: a single mutable knowledge file (there, `daca_knowledge_base.md`) got overwritten and 46 historical tickets were lost. Two independent "standard reply" sources that can silently drift is the same failure shape with extra steps; surfacing the diff is cheap insurance.
5. **Reply grounding prioritizes the actual client message over case-record inference.** `client_comms_agent._build_user_content()` puts the client's most recent message from the thread ahead of case status — answering a question the client didn't ask is a worse failure than a slightly less complete answer to the one they did.
6. **Every send returns a `SendReceipt`.** Not persisted yet (there's no event log/case register storage in this repo — see `REDESIGN_PROPOSALS.md` §1.3), but the shape exists now so wiring it to storage later is additive, not a rewrite. This is the harness property called out in `GUMLOOP_AGENT_REVIEW.md` Part A, failure #4: "fired actions whose completion is unknown."

## Before this touches a real ticket

1. Set `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN` (generate the token in Zendesk Admin → Apps & Integrations → Zendesk API).
2. Run `ZendeskClient.test_read()` — confirms read auth, raises immediately on a bad token rather than surfacing as a 401 mid-investigation later.
3. Run `ZendeskClient.test_write(owner_email=<your email>)` — creates an internal-only tagged ticket (`daca-ops-test`, `connection-check`). Confirm it in the Zendesk agent view, then close it.
4. Only then wire `client_comms_agent.generate_reply()` / `.send_reply()` into an actual case flow, and only with a real `anthropic_client` and an injected async HTTP client (e.g. `httpx.AsyncClient`) passed to `ZendeskClient`.

## Open items

- No storage yet for `SendReceipt` — needs the case register (`REDESIGN_PROPOSALS.md` §1.3) before receipts are durable rather than call-and-discard.
- `find_ticket_for_client()` has not been validated against Rho's actual Zendesk field/tag conventions for DACA-related tickets — confirm whether DACA client tickets use a distinguishing tag or form ID before relying on free-text search alone at volume.
- Attachment content (which documents get auto-suggested per reply type) is stubbed as a caller-supplied list (`SuggestedAttachment`) — not yet wired to pull the current WB-approved template automatically from `DocumentRecord`.
