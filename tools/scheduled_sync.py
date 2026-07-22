"""
Scheduled sync entrypoint — the "run without an agent in the loop" job (R12/Rhollout).

On Rhollout this is invoked on a schedule (Cloud Scheduler / cron). It pulls every
configured source (DACA Summary sheet, Salesforce, Jira, and Gmail intake), applies
the idempotent syncs, auto-posts new-request alerts to #daca-ops, and writes a
sync_run receipt — the same run_sync() the in-app "Refresh"/"Sync now" button calls.

Because the syncs are idempotent, running this every N minutes is safe: no duplicate
cases, events, or Slack pings. This is the polling model the deploy doc calls for
(inbound webhooks are firewalled on *.rho-preview.co, so we pull rather than receive).

Config comes entirely from the environment (Rhollout Secret Manager):
  DATABASE_URL                      Postgres DSN on Rhollout; falls back to the local
                                    SQLite register (DACA_REGISTER_DB) when unset.
  JIRA_* / SF_* / GOOGLE_* / GMAIL_* / TYPEFORM_TOKEN / SLACK_BOT_TOKEN / ...

USAGE:  python tools/scheduled_sync.py
"""

from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.register.db import Register
from src.register.sync_service import run_sync, build_sources_from_env


def main() -> int:
    db = os.environ.get("DATABASE_URL") or os.environ.get(
        "DACA_REGISTER_DB", "daca_register.db")
    reg = Register(db)
    report = run_sync(reg, build_sources_from_env(),
                      datetime.now(timezone.utc).isoformat())
    print(json.dumps(report, indent=2))
    # Non-zero exit if any configured source errored, so the scheduler surfaces it.
    ok = all(s.get("status") != "error" for s in report["sources"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
