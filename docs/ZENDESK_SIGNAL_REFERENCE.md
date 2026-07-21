# Zendesk Integration Reference (from Rho's "Signal" tool)

> Source: the Signal / `rho7005.zendesk.com` Zendesk integration guide, provided by
> the DRI as the reference for wiring the same integration into DACA Ops. This is the
> upstream how-to; the DACA-specific adaptation (human-gate, shared-queue cautions) is
> in `docs/ZENDESK_INTEGRATION.md` and the `zendesk-client-comms` skill.

Signal wires up Zendesk for authentication, org lookup, ticket creation, comments,
macros, and testing. Use this as the reference for adding the same integration elsewhere.

## 01 · Authentication

Signal uses **API token auth, not a password**. The auth header is built once at module
load from three env vars and reused across all requests:

```
const ZENDESK_AUTH = 'Basic ' +
  Buffer.from(`${ZENDESK_EMAIL}/token:${ZENDESK_API_TOKEN}`).toString('base64');
```

The **`/token:` separator** between email and token is required — it tags the credential
as an API token, not a password. **Omitting it causes silent 401s.**

| Env var | Value |
|---|---|
| `ZENDESK_SUBDOMAIN` | `rho7005` |
| `ZENDESK_EMAIL` | `patrick.cain@rho.co` |
| `ZENDESK_API_TOKEN` | Generate in Admin → Apps & Integrations → Zendesk API |

## 02 · Org lookup (before creating a ticket)

```
GET /api/v2/search.json
  ?query=type:organization "Acme Corp"
  &per_page=5
```

- The dedicated `/organizations/search` endpoint requires admin access Signal doesn't
  have, so it uses the **main search API** instead.
- Company names often carry trailing punctuation (`"Serenity Kids Inc."`) — **strip it**
  before searching.
- **Matching logic:** exact → name includes query → query includes name → first result.
  On any failure return `{ org: null, users: [] }` rather than erroring — the ticket can
  still be created without an org attached.

## 03 · Ticket creation

- **Return `500`, not `502`, on Zendesk errors.** Cloudflare intercepts 502 responses and
  replaces them with an HTML error page, which breaks JSON parsing on the frontend.
- After a successful create, immediately write `zendeskTicketId` and `zendeskTicketUrl`
  back to the case row (Signal persists to Postgres).

## 04/05 · Fetching a ticket and its thread

Fetch ticket metadata and its full comment thread **in parallel**, then return them
together in one response:

```
const [ticketRes, commentsRes] = await Promise.all([
  fetch(`.../tickets/${ticketId}.json`,          { headers }),
  fetch(`.../tickets/${ticketId}/comments.json`, { headers }),
]);
```

If the comments request fails, **degrade gracefully** — the ticket still renders with an
empty thread rather than erroring out.

## 06 · Macros (reply templates)

Pull active macros and surface them as pre-written reply templates in the case panel —
useful for standardizing common BSA/compliance responses:

```
GET /api/v2/macros.json?active=true&per_page=100
```

Each macro's `comment_value_html` action (or `comment_value` as fallback) is extracted and
**stripped of HTML tags** before display. Macros with no comment action are skipped.

## 07 · Testing the connection

Two endpoints confirm credentials work before touching real cases:

```
# Read check — fetches 1 ticket
GET /api/zendesk/test

# Write check — creates a tagged test ticket
POST /api/zendesk/test-ticket
```

The write check creates a ticket tagged `fraud-tm test connection-check`; confirm it lands
correctly in the Zendesk agent view. *(DACA note: our Zendesk is a live client-facing
queue, so the DACA adaptation makes the write-check ticket internal-only — see the
`zendesk-client-comms` skill.)*
