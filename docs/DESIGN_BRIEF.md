# DACA Ops — design-refinement brief

**Who this is for:** a design-focused session picking up the UI/UX of this app. The
build is functionally solid; this brief is about making it *look and feel*
production-grade. Read this first, then **run the app and look at it** (below) —
the visual reality is the real spec.

**Read these two for functional context (do not re-derive them):**
`docs/SESSION_2026-07-22_HANDOFF.md` and `.claude/skills/daca-ops-tool/SKILL.md`.
This brief assumes them.

> ⚠️ **PII rule (non-negotiable).** The register holds real client data. It is
> gitignored and rebuilt each session. **Never commit screenshots or exports that
> contain client names** to git. If you want the design session to see the current
> UI without live data, paste screenshots into that chat directly — don't add them
> to the repo. See `.claude/skills/daca-data-security`.

---

## 1. See it running (5 minutes)

```bash
git clone -b claude/nifty-darwin-rle1pt https://github.com/shaniabrahams-ctrl/DACA_Ops.git
cd DACA_Ops
./run_local.sh                 # http://127.0.0.1:8000  (creates .venv on first run)
```

The register DB is **not** in the download. Either:
- start with an empty register (the app still runs — you can add a net-new case), or
- re-seed from live sources in a session that has the Jira + Salesforce connectors:
  ```bash
  # produce jira.json / sf.json from the live sources (queries are in the master skill §2),
  # save them OUTSIDE the repo (e.g. a scratch dir), then:
  python tools/seed_register.py --jira /path/jira.json --salesforce /path/sf.json
  ```

Design is best judged against a populated register (~50 cases). If you only need
layout/visual work, the empty register plus one hand-added case is enough.

## 2. What the app is (one paragraph)

A single **register + guided-expert portal** that a *non-technical Rho ops rep*
uses to service DACA (Deposit Account Control Agreement) requests end to end. It
merges every system the process lives in (Google Sheet tracker, Salesforce, Jira,
Gmail) into one board, surfaces what needs a human, and walks the rep through each
SOP step. The primary user is **not** an engineer — the UI must read in plain
English and never expose internal jargon.

## 3. Screen inventory (what exists today)

| Route | Screen | Purpose |
|---|---|---|
| `/` | **Dashboard** | New-requests-to-triage band; KPI tiles (In flight / At risk / Action items / Active); a plain-English **"What needs you"** action queue side-by-side with an **"In flight"** end-to-end progress list; collapsible Active + Off-pipeline sections. |
| `/register` | **All DACAs** | The tracker-replacement table (search; columns: Rho ID, Business name, Stage, Lender, Agreement, Completion, Tickets, Attention). Deep-links to Jira/LEGALHELP. |
| `/case/{id}` | **Case detail** | Status pills; needs-attention banner w/ in-app Resolve; 9-step **Stage tracker**; **Guided next step** (SOP phase, owner, checklist, "advances when", Draft-email + Drive buttons); Client comms (Zendesk); Draft-a-reply; append-only **Timeline**; right rail: Sources, Advance stage, Set next action, Parties. |
| `/reports/webster` | **Webster report** | The monthly Rho↔Webster report: "Draft — not sent" gate, status counts, Download PDF/XLSX, a "Review before sending" data-quality list, the full DACAs List table, and the covering-email draft. |
| `/sync` | **Sync** | Source-credential status + recent-run log. (In-app sync is live only when the deploy has source creds.) |

## 4. Product/UX principles to PRESERVE (these are load-bearing, not up for redesign)

1. **Human-centered, plain English.** No engineer jargon in the UI (never show raw
   `source_conflict:` / enum names to the rep). The action queue already translates
   these — keep that discipline in any new surface.
2. **At-a-glance first.** The rep should see "what needs me and where is everything"
   without reading. KPIs + action queue + progress tracks carry that load.
3. **End-to-end progress is the spine.** Every in-flight case shows step X/9, what's
   now, what's next, how many steps to Active. Don't lose this in a redesign.
4. **Human-gate only on outward/irreversible actions** (client email, Webster send,
   DocuSign, live Jira create) — these are *draft-then-send*. Internal register
   updates and ops notifications are automatic and should feel effortless, not gated.
5. **No-infer.** Missing data is shown blank + flagged, never guessed. Don't design
   placeholder values that could read as real.
6. **Teal, sparingly.** Caribbean teal (`--carib-500 #07EBC0`) is the one hero
   accent — used for "good/active/current" and primary hover only. White + black +
   teal. Don't spread accent color around.

## 5. Current design system (what you're working within)

- **Rendering:** FastAPI + **Jinja2 server-rendered templates**. No React, no build
  step, no JS framework. Templates in `src/webapp/templates/`
  (`base.html`, `board.html`, `case.html`, `register.html`, `reports_webster.html`,
  `sync.html`).
- **CSS:** a **single inline `<style>` block in `base.html`** — CSS custom
  properties + hand-written classes. There is no external stylesheet. Any new styling
  goes here (or a linked static file if you introduce one — see constraints).
- **Tokens** (already defined in `base.html`): Moon (whites), Abyss (blacks/greys),
  Caribbean (teal), Mist (muted). Semantic: `--bg --surface --ink --muted --line
  --accent`; state `--ok/--warn/--flag`; spacing scale `--sp-1..8` (4→48px); `--radius`
  12px / `--radius-sm` 8px; soft `--shadow`; 200ms transitions; font stack is Basier
  Circle → Inter → system.
- **Light + dark** both defined via `prefers-color-scheme`.
- **Components already built:** `.card .kpi .pill .btn .funnel .stepper .track
  .wq-col .action .kanban .panel .split .thread .bubble` + table styles. Reuse these
  before inventing new ones.
- **Brand source of truth:** Rho Brand Guidelines V3.2 (Notion
  `369db9eb-a4f0-814c-b255-d4b22012ad51`) + LLM Style Guide (`1addb9eb-a4f0-803b-813e-fc7ae5c4950c`):
  sentence case, left-aligned, generous whitespace, soft shadows.

## 6. Constraints a redesign must respect

- **Deploys to Rhollout** (internal Rho PaaS), VPN-only, gateway-locked. Keep it a
  server-rendered app that runs behind that gateway — don't take a hard dependency on
  external CDNs, web fonts from third parties, or client-side frameworks that
  complicate the deploy. Self-contained is a feature here.
- **Accessibility:** it's an internal operations tool used all day — legibility,
  focus states (already present via `:focus-visible`), and colour-contrast in *both*
  themes matter more than flourish.
- **Server-rendered:** interactions are mostly full-page GET/POST + a little
  `<details>`. If you add client-side interactivity, keep it progressive and inline.

## 7. Honest read of what needs design work (starting targets — verify against the live app)

These are the current session's observations; treat as hypotheses, not gospel.

1. **Case page is very long and single-column-heavy.** It's a tall vertical stack;
   the left column runs out of content while the right rail continues, leaving
   unbalanced whitespace. The primary action (**Advance stage**) sits low in the
   right rail, often below the fold. Consider: sticky action rail, or promoting the
   next-step action nearer the top.
2. **Density on "All DACAs."** Business name + lender wrap onto multiple lines,
   making rows tall and the table hard to scan. Tighten row height / column widths;
   consider a sticky table header for the long list.
3. **Webster list is 44+ rows with no sticky header** — scanning the table loses the
   column labels. Same for long dashboard sections.
4. **KPI tiles vs. new-requests band** compete for the top of the dashboard; the
   hierarchy of "triage this now" vs. "here are the numbers" could be sharpened.
5. **Empty/again states.** "Parties: None recorded yet", "Zendesk isn't connected"
   — these are honest but visually flat; they could guide the user to the next action.
6. **Mobile/responsive** is only lightly handled (`.split` collapses at 900px). If
   reps use this on smaller screens, that needs attention.

## 8. What NOT to touch

The **functional correctness** is the product's whole value (see the master skill's
success criteria: human touchpoints are approvals, not corrections). Don't change:
register/merge logic, the state machine and transition rules, the no-infer behaviour,
the human-approval gates, or the source identifiers. This is a **skin + layout +
interaction** refinement, not a rebuild.

## 9. Useful tools for the design session (if it's a Claude session)

- **`rho-spacing-review`** skill — validates spacing against Rho's design system;
  point it at screenshots of these screens.
- **`dataviz`** skill — before touching the KPI tiles / progress tracks / any chart.
- **`artifact-design`** — if you prototype a redesigned screen as a standalone
  artifact before porting it into the Jinja templates.
- **`rho-org-structure`** — to decode any Rho names/roles referenced in the app.
