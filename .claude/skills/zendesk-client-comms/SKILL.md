---
name: zendesk-client-comms
description: How DACA Ops does client-facing communication over Zendesk — authentication, ticket lookup, reading a thread, macros as reply templates, and sending a human-approved reply. Use this whenever building, wiring, operating, or debugging the client-comms feature (the case-page comms panel, the ZendeskClient, or the client_comms_agent). Zendesk is the client-facing channel; Jira/CSHELP is internal tracking — never conflate them.
---

# DACA Ops — Zendesk Client Comms

Zendesk is where the **client** writes in and where Rho replies, attaches documents, and
shares SendSafely links. Jira/CSHELP is internal case tracking — a different surface.
A case can carry both; one never implies the other.

**Reference:** `docs/ZENDESK_SIGNAL_REFERENCE.md` (the upstream Signal how-to) and
`docs/ZENDESK_INTEGRATION.md` (the DACA-specific design). Code:
`src/integrations/zendesk_client.py` (transport) and `src/agents/client_comms_agent.py`
(draft + gated send). The web wiring is the case-page comms panel.

## Authentication (get this exact, or you get silent 401s)

API token auth, **not** a password. Header built once from three env vars and reused:
`Basic base64("<ZENDESK_EMAIL>/token:<ZENDESK_API_TOKEN>")`. The **`/token:` separator is
mandatory** — omit it and Zendesk returns a silent 401, not a helpful error.

| Env var | Notes |
|---|---|
| `ZENDESK_SUBDOMAIN` | e.g. `rho7005` → `https://rho7005.zendesk.com/api/v2` |
| `ZENDESK_EMAIL` | the API account (currently `patrick.cain@rho.co`) |
| `ZENDESK_API_TOKEN` | secret — Admin → Apps & Integrations → Zendesk API. Never commit; local `.env` / Rhollout Secret Manager. |

If any are unset, the app must show a "Zendesk not connected" state, not crash.

## The operations, and the rules that matter

1. **Ticket lookup via the general search API**, not `/organizations/search` (needs admin
   scope a service account may lack). Prefer requester email (precise), fall back to entity
   name; strip trailing punctuation (`"Serenity Kids Inc."`). Match: exact → subject
   contains → first result. Return None on miss/failure — a case may have no ticket yet.
2. **Read the thread with graceful degradation.** Fetch ticket + comments in parallel; if
   comments fail, still render the ticket with an empty thread.
3. **Macros = reply templates, and a drift check.** Pull `macros.json?active=true`; extract
   `comment_value_html`/`comment_value`, strip HTML. These are surfaced for convenience and
   to spot drift against the git-versioned SOP wording — they are NOT the authoritative
   reply source (that's `email_drafter.py`, per GUMLOOP_AGENT_REVIEW #3).
4. **Human gate on every send — non-negotiable.** `ZendeskClient.post_comment` /
   `create_ticket` require a non-empty `approved_by` (enforced in the signature, not by
   convention). The ONLY sanctioned send path is `client_comms_agent.send_reply(zendesk,
   ticket_id, approved_text, approved_by, ...)`. In the app, `approved_by` is the
   logged-in operator and the send happens only on their explicit click. Never auto-send.
5. **Our Zendesk is a live, shared, client-facing queue.** Unlike Signal's internal
   fraud-TM instance, real clients see this queue. So the write-connection-check creates a
   ticket with an **internal-only** comment (`public=False`) + tags, and it must be closed
   after eyeballing — don't accumulate test tickets clients can see.
6. **Proxy/status gotcha:** map Zendesk errors to a `500`, never a `502` — Cloudflare
   replaces 502 bodies with an HTML error page that breaks JSON parsing downstream.
7. **Sensitive documents go through SendSafely**, not raw Zendesk/email attachments — embed
   `build_sendsafely_block()` (dropzone `https://rho.sendsafely.com/dropzone/daca`) when
   asking a client for SSNs / account numbers / IDs. (daca-data-security: RESTRICTED data
   never flows through the app.)

## When wiring into the app

- Look up the ticket live per request (view-don't-store); pass the borrower contact email
  when known. Don't cache thread content to the register — it's client PII.
- Every send appends a receipt event to the case (`client_reply_sent`) with the
  `approved_by` operator and the returned `comment_id` — receipts are how silent failures
  get caught (GUMLOOP_AGENT_REVIEW Part D).
- AI-drafting (`client_comms_agent.generate_reply`) needs an Anthropic key + the case
  thread; keep it a draft-only step feeding the same compose box the human edits and sends.
