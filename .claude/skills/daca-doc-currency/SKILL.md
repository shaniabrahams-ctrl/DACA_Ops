---
name: daca-doc-currency
description: Audit all DACA-related documentation (Notion SOPs, the Webster-facing Operations Manual, templates, compliance/affirmation requirements, tracker conventions) for accuracy and currency against actual process changes; produce a drift report and proposed updates for human review. Run at least once per quarter, or after any announced process change.
---

# DACA Documentation Currency Review

You are auditing Rho's DACA documentation for drift between **what the documents say** and **how the process actually runs**. The output is a drift report plus proposed edits — **never publish, overwrite, or send any document yourself**. The DACA DRI reviews and applies/approves every change. The Webster-facing manual additionally requires DRI sign-off before anything is shared externally, since Webster requested that document.

## Document inventory (the audit scope)

| Doc | Location | Audience |
|---|---|---|
| Rho DACA Process (master SOP) | Notion `245db9eb-a4f0-800c-816c-cb5a02133f81` | Internal |
| DACA trigger event playbook | Notion `36ddb9eb-a4f0-806e-be42-d3f6994a86de` | Internal |
| DACA (agreement) Termination Process | Notion `36ddb9eb-a4f0-8025-bde2-f14e58a1471f` | Internal |
| DACA Redlining Eligibility Guidelines | Notion `348db9eb-a4f0-80a8-9b30-e7abf15ddd0d` | Internal + shared with Webster |
| Webster Approved DACA Template | Drive folder `1OdKr5BVGkAME64_nEm4nkYuVxHjzUc2-` (current: 10.24.25) | External |
| **Rho DACA Operations Manual (Webster-facing guide)** | Drive folder `1uB1PnEMnGhrrvDzO-jZXnwVYKBfr0I8C` (current: vMar26) | **External — Webster requested this** |
| DACA Compliance Package Requirements | Drive doc `1p51X0rNIf1IFzImSNWTrwjXV2zcakzo5_2tQpyd-aMU` | Internal |
| DACA Summary tracker conventions / WebsterReport tab | Sheet `140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls` | Internal / report feeds Webster |
| Outdated pages that must stay marked outdated | Notion "DACA Set Up Process OUTDATED", "DACA Playbook" (2025), Drive `Operations Manual/previous versions/` | — |

If new DACA docs appear (search Notion + the DACA Drive root `121c4-xohOHgK8J_-vX-I-Mfoc7nTR3mX` for additions since last run), add them to this table as part of the run.

## Procedure

1. **Collect change signals since the last review** (or last 90 days):
   - Notion: `last_edited_time` on each inventory page; diff content if changed.
   - Slack #daca-applications + #daca-ops: announcements of process changes (e.g., the 4/20 compliance-packet→affirmation announcement), policy decisions in threads.
   - Jira: DACA-affecting ENG/process tickets closed in the window (search `text ~ "DACA" ORDER BY updated DESC` across CSHELP/ENG/COMPLHELP/FRAUDTM).
   - Gmail (daca@rho.co): Webster communications that change requirements (contacts, signatories, submission steps, fees).
   - The case register event log, once it exists (preferred signal source).
2. **For each inventory doc**, check every signal against its content. A doc is **drifted** when it states something a signal contradicts, and **stale** when it omits a change it should describe.
3. **Cross-consistency checks** (docs vs each other): SOP vs trigger playbook (account conversion policy), SOP vs affirmation requirements (compliance package vs one-page affirmation), SOP contact tables vs actual Webster/DocuSign recipients in recent sends, template version referenced everywhere vs the file in the Webster Approved folder, language rules (no "survey"/"questionnaire" anywhere — including folder names).
4. **Verify with evidence**: every flagged drift must cite its source (message permalink, email, Jira key, page diff). Never flag from memory; never propose a change you cannot evidence. If a signal is ambiguous (e.g., announced but possibly not yet effective), list it as a **question for the DRI**, not a finding.
5. **Produce the drift report** (format below) and, for each confirmed drift, a ready-to-apply proposed edit (exact old text → new text). For the Webster-facing manual, prepare a tracked-changes summary the DRI can review before any new version is saved to `Operations Manual/` (save as a NEW version file, e.g. `vJun26`; move the old one to `previous versions/` — never edit in place).

## Drift report format

```
# DACA Documentation Currency Report — <date>
Window reviewed: <date range> · Docs checked: N · Drifts: N · Questions: N

## Confirmed drift (evidence-backed)
1. <Doc> §<section>: says "<current text>" but <signal + link> changed this on <date>.
   Proposed edit: <old → new>. Severity: <external-facing | SLA/safety | internal-only>.

## Open questions for DRI
1. <ambiguous signal, what needs confirming, link>

## Verified current (spot-checked, no action)
- <doc>: checked against <signals>; consistent.
```

Deliver the report to the DRI (Shani Abrahams) for review — in chat, plus committed to `docs/doc-currency-reports/<YYYY-QN>.md` in the DACA_Ops repo for the audit trail. External-facing drift (Operations Manual, template, redlining guidelines) is always the top section.

## Known drift seeds (found 2026-06-10 — verify, don't assume still open)

- Operations Manual **vMar26** predates: the 4/20 compliance-packet→**affirmation** change, the 4/20 redline-fee option, and the 6/1 trigger-playbook policy (no default pre-conversion; multi-account path). Likely needs a new version for Webster.
- Master SOP (edited 5/27) still documents full compliance-package assembly (Middesk/Alloy/UBO checklist) with no mention of the affirmation path — confirm which regime is actually in force with Compliance before proposing the edit.
- Drive folder `DACA Documents/Surveys/` violates the language rule.
- Termination SOP's required filing location (`Termination Agreements/` subfolder) has had no filings since 2023 despite the 5/15/26 Champion termination — either the SOP or the practice must change.

## Cadence

Minimum **once per quarter** (target: first week of Jan/Apr/Jul/Oct), plus an immediate targeted run after any announced process change or Webster requirement change. This skill defines the procedure; the schedule itself must be enforced by a scheduler (DACA Ops app scheduler once built; until then a recurring calendar/Slack reminder to invoke `/daca-doc-currency`). A quarter with no report committed to `docs/doc-currency-reports/` is itself a finding.
