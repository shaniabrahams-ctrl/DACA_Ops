"""
Backfill loan agreements from the DACA application Typeform responses into Drive.

For each response that has a real uploaded file, download it from Typeform and file
it into the borrower's client folder in Drive, leaving a receipt on the case. Same
decoupled shape as tools/seed_register.py: you supply a text snapshot of the
Typeform responses sheet; the clients do the live I/O.

CREDENTIALS (never committed):
  TYPEFORM_TOKEN                 Personal Access Token, scope responses:read
  GOOGLE_APPLICATION_CREDENTIALS path to a Drive service-account JSON (write access)

USAGE:
  # Dry run — parse + classify + match only; NO token/creds needed, downloads nothing.
  python tools/backfill_loan_agreements.py --responses typeform.md --dry-run

  # Real run — needs TYPEFORM_TOKEN + GOOGLE_APPLICATION_CREDENTIALS in the env.
  python tools/backfill_loan_agreements.py --responses typeform.md --db daca_register.db

HOW TO GET THE SNAPSHOT: read the "DACA Application Form - Typeform Responses" sheet
(Drive id 1Oog92OTZ5w4Lss-CSVJ-jos8d4Or3K8qu6EQe0EuvtE) and save its text/markdown.
The snapshot holds client data → keep it in a scratch path, never commit it.
"""

from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.register.db import Register
from src.operations import loan_agreements as la


def _dry_run(reg: Register, responses: list[dict]) -> None:
    """Report what WOULD happen without downloading/uploading anything (no token)."""
    filed = skipped = unmatched = 0
    print(f"DRY RUN — {len(responses)} responses parsed\n")
    for r in responses:
        url = la.extract_file_url(r["upload_cell"])
        if not url:
            skipped += 1
            continue
        case = la.match_case(reg, r["borrower_name"])
        if case:
            filed += 1
            print(f"  FILE   {r['borrower_name'][:38]:38} → {case.business_id} - "
                  f"{case.entity_legal_name[:30]}  ({url.rsplit('/', 1)[-1][:40]})")
        else:
            unmatched += 1
            print(f"  FLAG   {r['borrower_name'][:38]:38} → no case match — holding folder + review")
    print(f"\n  would file (matched): {filed} | unmatched→flag: {unmatched} | "
          f"skipped (no file link): {skipped}")


def main():
    ap = argparse.ArgumentParser(description="Backfill Typeform loan agreements into Drive.")
    ap.add_argument("--responses", required=True, help="Path to the Typeform responses sheet text")
    ap.add_argument("--db", default="daca_register.db", help="Register path")
    ap.add_argument("--dry-run", action="store_true", help="Parse/classify/match only; no I/O")
    ap.add_argument("--no-create-missing", action="store_true",
                    help="Do not create client folders; skip+flag unmatched instead")
    args = ap.parse_args()

    with open(args.responses) as f:
        responses = la.parse_responses(f.read())
    reg = Register(args.db)

    if args.dry_run:
        _dry_run(reg, responses)
        return

    from src.integrations.typeform_client import TypeformClient
    from src.integrations.drive_writer import GoogleDriveWriter
    now = datetime.now(timezone.utc).isoformat()
    result = la.process_loan_agreements(
        reg, responses, TypeformClient(), GoogleDriveWriter(),
        now_iso=now, create_missing=not args.no_create_missing)

    s = result.summary()
    print(f"Loan agreements: filed {s['filed']}, already-on-file {s['already_filed']}, "
          f"skipped {s['skipped']}, flagged {s['flagged']}, errors {s['errors']}")
    for f in result.filed:
        print(f"  filed   {f['case_id']}: {f['filename']}")
    for f in result.flagged:
        print(f"  flagged {f.get('case_id')}: {f['reason']}")
    for e in result.errors:
        print(f"  ERROR   {e['borrower']}: {e['error']}")


if __name__ == "__main__":
    main()
