"""
Seed / refresh the DACA case register from live-source snapshots.

WHY THIS EXISTS: the register holds real client data, so it is never committed to
git and never shipped as a binary. Instead you rebuild it locally from JSON
snapshots of the live sources. This keeps the repo PII-free (daca-data-security
skill) while letting anyone reproduce the real register on their own machine.

INPUTS (JSON files you produce from the live sources — see "HOW TO GET THE JSON"):
  --jira      path to the Atlassian search result for CSHELP "DACA Request" tickets
              (the raw response shape: {"issues": {"nodes": [ {key, fields}, ... ]}})
  --salesforce path to the SOQL result for Account DACA fields
              (the raw response shape: {"records": [ {Name, Business_ID__c, ...}, ...]})
  --db        output register path (default: ./daca_register.db)

HOW TO GET THE JSON (two ways):
  1. Ask your Claude/agent session (the one with Jira + Salesforce connectors) to run:
       - Jira:  JQL  project = CSHELP AND issuetype = "DACA Request" ORDER BY updated DESC
                fields: key, summary, status, created, updated, labels, assignee
       - SF:    SOQL SELECT Name, Business_ID__c, DACA_Status__c, DACA_Type__c,
                DACA_Agreement_Date__c FROM Account WHERE DACA_Status__c != null
     …and save each raw result to a .json file next to this script.
  2. Or, once Rhollout is live, the scheduled sync job does this automatically with
     service credentials — this script is the same logic, run by hand for local dev.

Idempotent: re-running against the same snapshots produces no duplicate events.

USAGE:
    python tools/seed_register.py --jira jira.json --salesforce sf.json
    python tools/seed_register.py --jira jira.json          # Jira only is fine
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timezone

# make 'src' importable when run from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.register.db import Register
from src.register.sync_jira import sync_all
from src.register.sync_salesforce import sync_salesforce


def _load(path: str):
    with open(path) as f:
        return json.load(f)


def _jira_nodes(payload) -> list[dict]:
    # accept either the full response or a bare list
    if isinstance(payload, list):
        return payload
    return payload.get("issues", {}).get("nodes", payload.get("nodes", []))


def _sf_records(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    return payload.get("records", [])


def main():
    ap = argparse.ArgumentParser(description="Seed the DACA register from live snapshots.")
    ap.add_argument("--jira", help="Path to Jira DACA-Request search result JSON")
    ap.add_argument("--salesforce", help="Path to Salesforce DACA accounts SOQL result JSON")
    ap.add_argument("--db", default="daca_register.db", help="Output register path")
    args = ap.parse_args()

    if not args.jira and not args.salesforce:
        ap.error("provide at least --jira (and optionally --salesforce)")

    now = datetime.now(timezone.utc).isoformat()
    reg = Register(args.db)

    if args.jira:
        tickets = _jira_nodes(_load(args.jira))
        report = sync_all(reg, tickets, now)
        print(f"Jira: {report['tickets']} tickets → "
              f"{report['created']} created, {report['updated']} updated, "
              f"{report['unchanged']} unchanged")

    if args.salesforce:
        sf = _sf_records(_load(args.salesforce))
        r = sync_salesforce(reg, sf, now)
        print(f"Salesforce: {len(sf)} DACA accounts → "
              f"{r['enriched']} enriched, {r['reconciled']} reconciled, {r['flagged']} flagged")

    total = len(reg.all_cases())
    print(f"Register ready at {args.db} — {total} cases.")


if __name__ == "__main__":
    main()
