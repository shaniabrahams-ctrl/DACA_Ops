# Feasibility Assessment: Agent-Run DACA Process

**Date:** 2026-06-10 · Grounded in: the systems sweep (Jira/Gmail/Notion/Slack/Drive), the three Gumloop agent reviews, the SOP corpus, and current Claude model pricing/capabilities.

## Scores

| Mode | Confidence | Verdict |
|---|---|---|
| **Fully autonomous end-to-end** | **2/10** | Not achievable and not the right goal — blocked by structurally human steps, not model capability |
| **HITL, human as verifier only** | **7/10** | Achievable for ~60–70% of DRI workload, conditional on the register being built first and system-access gaps resolved; the remaining ~30% is irreducibly human *work*, not review |

## Why full autonomy caps at 2/10

Four steps are **constitutionally human** — they don't improve with better models:
1. **The CFO's signature.** Mike Szarowicz signs every DACA as Rho's representative. A legal signature on a four-party banking agreement cannot be delegated to an agent.
2. **Compliance attestation.** The new one-page affirmation to Webster is an accountability act by a regulated institution's compliance function. Webster accepts it because a human stands behind it.
3. **Legal negotiation.** Redlines (the Anonos lane) are negotiated between Rho Legal, Webster Legal, and client counsel. An agent can coordinate and chase; it cannot be Rho's lawyer.
4. **Trigger events and terminations** transfer control of client funds, are adversarial by design (documented social-engineering risk in the termination SOP), irreversible, and bank-partner-facing. No responsible design — and likely no banking partner — gives an agent unilateral authority here.

Plus two practical blockers: **RAP actions are documented as manual UI click-paths** (impersonate client, TCT lookups, deactivate/block buttons) with no evidence of API access; and **the process itself contains unresolved ambiguities** (affirmation vs. compliance packet; whether trigger role-reversal is legally required; who may terminate) — an agent cannot be more accurate than ground truth that doesn't exist.

## Why HITL lands at 7/10 (not higher, not lower)

**High confidence (8–9/10), most of the workload by volume** — intake/qualification, drafting from approved macros, status tracking and the pipeline surface, weekly/monthly reporting, document filing with receipts, DocuSign prep + webhook bookkeeping, follow-up chasing. These are classifiable, template-driven, evidence-checkable — exactly what the mailbox taxonomy shows fills the day.

**Medium confidence (5–6/10)** — affirmation evidence assembly (agent gathers, human attests), novel client/lender questions (agent drafts, human edits — quality will vary), redline coordination (agent tracks deadlines and drafts chases; humans negotiate).

**Honest caveats that cap the score:**
- "Minimal manual work besides review" is reachable for the covered workflows, but the human still *does* (not reviews): legal negotiation, Webster relationship calls, RAP clicks (until API access exists), signing, and exception judgment (e.g., the "do not approve clients like this" tier decisions in the tracker).
- ~44 cases all-time, a handful concurrent: the novel-case tail is large relative to volume, and there's limited repetition to validate against. Mitigation: an eval set built from the historical cases + shadow mode, not learn-on-the-job.
- Three prior agents failed at narrower scopes. The failures were architectural (no idempotency, no receipts, mutable memory) and the new design addresses each one specifically — but the base rate demands shadow-mode proof, not optimism.
- Counterparty latency (Webster Legal, client signers) dominates cycle time; automation compresses Rho-side hours, not Webster-side days.

## Weak spots (ranked)

1. **Process ground truth is ambiguous.** Affirmation vs. packet regime unconfirmed; trigger role-reversal legality open (Sam); termination rights partially open. Agent accuracy is bounded by SOP accuracy. → Resolve via the doc-currency run before building workflows on either answer.
2. **System access for the highest-stakes actions.** RAP/TCT/Unit 21 are manual UI surfaces. Until eng provides APIs (Rishi questions in the trigger playbook), the human remains the "hands" for account actions — fine for HITL, fatal for autonomy claims.
3. **Data foundation.** The tracker's 10 documented defects mean any agent built on it industrializes garbage. Register first, automation second.
4. **Trigger/termination adversarial window.** 2-hour SLA, social-engineering motive, multi-account exposure gap between deactivation and Unit 21 rules. Agent value = instant verification-evidence assembly; decision = human, always.
5. **Single-DRI concentration.** Everything routes through one person (the monthly reporter literally hardcodes her name). Dead-man switches + config-driven backups are required, or the agent inherits the bus-factor.
6. **Trust deficit.** The team has already learned to discount bot output (duplicate alerts, empty messages). First shipped workflow must be boringly reliable or adoption dies.

## Model economics (build on Fable, run on cheaper)

Current pricing (per MTok, input/output): **Fable 5 $10/$50 · Sonnet 4.6 $3/$15 · Haiku 4.5 $1/$5**; batch API −50%; cached prefix reads ~0.1×.

The architecture is what makes the downgrade survivable — this is the deliberate consequence of the harness-first design:
- **Deterministic code does most of the work for free**: webhooks, idempotency, state transitions, report rendering, filing, SLA clocks consume zero tokens regardless of model.
- **LLM calls become narrow and verifiable**: classify an inbound email, extract fields into a strict schema, fill an approved macro. These are Haiku 4.5-shaped tasks, enforced with structured outputs + strict tools, checked by code-level verifiers — the model proposes, the harness validates.
- **Tiered routing**: Haiku 4.5 for routine classification/extraction/templated drafting → Sonnet 4.6 for free-form drafting and ambiguous classification → human (or a frontier call) for the rare genuinely novel case. Prompt-cache the stable knowledge prefix; batch the non-urgent generation (monthly report) at half price.
- **The gate for each downgrade is the eval suite**, not vibes: golden cases from the 44 historical DACAs, measured per-model before any tier switch. The failure mode to avoid is porting a Fable-tuned free-form agent prompt onto Haiku and hoping — that is precisely the Gumloop pattern with a cheaper engine.
- Estimated steady-state inference cost at current volume (handful of active cases, tens of emails/week, weekly+monthly reports): **single-digit dollars per month** on the Haiku/Sonnet tiers with caching. Cost is not the constraint; correctness is.

## Bottom line

Autonomous: 2/10 — don't chase it; several steps are human by law, contract, and bank-partner expectation. HITL-with-verification: 7/10 today, and the conditions that would push it to 8–9 are all in our control: build the register first, resolve the affirmation/trigger ambiguities, get eng partnership on RAP access, ship workflow-by-workflow in shadow mode with receipts, and gate every model-tier decision on the historical-case eval suite.
