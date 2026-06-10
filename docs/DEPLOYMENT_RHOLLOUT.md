# Deployment Plan: DACA Ops on Rhollout

**Date:** 2026-06-10 · **Sources:** Rhollout Slack app how-to guide (Notion, edited 6/9), #rhollout-help channel history.
**Status:** Plan — nothing provisioned yet. ⚠️ `UnderTechnologies/rho-claude-skills` could not be accessed from this session (private repo outside session scope) — Rho's internal Claude-skills conventions must be reviewed before finalizing agent implementation details.

## 1. What Rhollout gives us

Rho's internal platform for preview apps, managed entirely from Slack (`/rhollout …`):

| Resource | Detail | DACA Ops use |
|---|---|---|
| GitHub repo | `rhollout-{name}` in **UnderTechnologiesLabs** org, from a Node.js / **Python** / Go template | App codebase (separate from this DACA_Ops planning repo) |
| Cloud Run service | Auto-scaling, at `{name}.rho-preview.co` (**VPN-only**) | The HITL app + agent workers |
| PostgreSQL | Own DB on shared CloudSQL, **IAM auth (no credentials)**, pre-wired in template | **The case register + append-only event log** — exactly the durable, queryable home the design needs |
| GCP Secret Manager | `/rhollout secret create\|update\|delete` | `ANTHROPIC_API_KEY`, DocuSign JWT creds, Typeform/Slack tokens |
| CI/CD | Merge to main → auto-deploy | Ship workflow-by-workflow |
| Static inbound + outbound IPs | Outbound usable for 3rd-party IP allowlisting | DocuSign/bank-side allowlisting if needed |
| Auth gateway | Google sign-in wall, default all `@rho.co`; can restrict to named users; 3h sessions | **Must restrict to named users** — DACA data is sensitive client/lender info |
| Collaborators | Secrets/gateway/logs access without destroy rights | Backup coverage (continuity requirement) |
| Logs | `/rhollout logs <app> [N≤500]` | Debugging |

Prereqs: Slack workspace, **GitHub account in UnderTechnologiesLabs org**, VPN for testing. TTL is 1 year with a 30-day warning. DNS mapping is manual by the builder-experience team (1–2 days) — the long pole, so provision early.

## 2. Critical constraints discovered

1. **Inbound webhooks are likely blocked.** `*.rho-preview.co` is VPN-only, and #rhollout-help shows external inbound being firewalled (Maher's MCP server never received Claude's POSTs from Anthropic's published IP range, 5/19). **DocuSign Connect and Typeform webhooks may not be able to reach the app.** → Question #1 for #rhollout-help / #tech-builder-experience: can specific external IP ranges (DocuSign Connect, Typeform) be allowed to a webhook path, or do we fall back to **polling** (DocuSign envelope-status polling + Typeform responses API polling)? The architecture supports either; webhooks are cleaner, polling is acceptable at our volume (5-min cadence ≈ the current Gumloop trigger).
2. **Env-var clobbering pitfall** (Ned, 5/26): the template `cd.yml` with `--set-env-vars` wipes Cloud-Run env vars on deploy — use `--update-env-vars`, and keep all config in Secret Manager rather than raw env vars where possible.
3. **Default gateway = all of rho.co.** For DACA, immediately: `gateway allow` the named team (DRI, Mike, Zorica, CS backup, Compliance), then `gateway deny @rho.co`.
4. **Preview-tier, not production-tier.** Rhollout is "Rho's tool for spinning up preview environments" (WIP per its own docs). Fine for the internal HITL rollout; the production system of record posture (backups, retention, audit guarantees for the register) should be confirmed with the platform team before the register becomes the sole source of truth — until then, the Drive/Sheet exports remain belt-and-suspenders.

## 3. Rollout sequence

| # | Step | Who | Notes |
|---|---|---|---|
| 0 | Get `rho-claude-skills` reviewable | Shani | Add the repo to a Claude session's scope, or export its contents — agent conventions must be followed |
| 1 | Confirm GitHub membership in UnderTechnologiesLabs | Shani | Prereq for create |
| 2 | `/rhollout create` → name **`daca-ops`**, runtime **Python**, your GitHub user | Shani | Creates `rhollout-daca-ops` repo + infra in 1–3 min |
| 3 | DNS wait (builder-experience team) | — | 1–2 days; code can be pushed meanwhile |
| 4 | Lock the gateway: `allow` named users → `deny @rho.co` | Shani | Before any real data exists |
| 5 | `/rhollout collaborator add daca-ops` for backup coverage | Shani | Continuity requirement |
| 6 | Ask the webhook-ingress question (§2.1) in #rhollout-help | Shani (I draft) | Decides webhook vs polling architecture |
| 7 | Secrets: `ANTHROPIC_API_KEY`, DocuSign integration key/user/private key, Typeform/Slack tokens | Shani (I provide exact list) | Via `/rhollout secret create` |
| 8 | Add `rhollout-daca-ops` to Claude session scope; I scaffold: schema (cases/parties/accounts/events/documents), migrations, FastAPI app, harness skeleton | Claude | Spec in this repo's docs govern the build |
| 9 | Ship workflow 1 in shadow mode (per GUMLOOP_AGENT_REVIEW Part A §4 / B4 order) | Claude + Shani | Register + pipeline surface first |

## 4. Open items

- [ ] `rho-claude-skills` contents reviewed and conventions adopted
- [ ] Webhook ingress vs. polling decision (blocks DocuSign/Typeform integration shape)
- [ ] Runtime confirmation (recommendation: **Python/FastAPI** — best fit for the data-heavy register, first-class Anthropic SDK, and the team's existing tooling)
- [ ] Production-posture confirmation for the register DB (backups/retention)
- [ ] App name confirmation (`daca-ops`; reserved names exclude it, format valid)
