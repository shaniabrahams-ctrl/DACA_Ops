"""
Run a live register sync from the command line (R12).

Same logic as the /sync route and the Rhollout scheduled job — pulls Jira +
Salesforce + the DACA Summary sheet via the source clients and applies the syncs.
Reads credentials from the environment (local .env / Secret Manager).

USAGE:
    python tools/sync_now.py            # sync into ./daca_register.db
    python tools/sync_now.py --db path  # sync into a specific register
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.register.db import Register
from src.register.sync_service import run_sync, build_sources_from_env


def main():
    ap = argparse.ArgumentParser(description="Refresh the register from live sources.")
    ap.add_argument("--db", default="daca_register.db")
    args = ap.parse_args()

    reg = Register(args.db)
    report = run_sync(reg, build_sources_from_env(), datetime.now(timezone.utc).isoformat())
    print(json.dumps(report, indent=2))
    if not report["any_configured"]:
        print("\nNo sources configured — set creds (see tools/sync_now.py docstring).")


if __name__ == "__main__":
    main()
