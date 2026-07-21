"""
Gmail source client — pull net-new DACA inquiries from the daca@rho.co inbox.

A new request often arrives only as an email (Client Service loops the DACA team into
a client thread) before any Jira ticket or tracker row exists. This client finds those
threads and returns them in the shape src/register/intake_email.sync_email_intake
consumes, so email becomes a first-class sync source alongside the sheet/SF/Jira.

DETECTION (kept conservative — no-infer): a thread is treated as a net-new inquiry when
it is recent, addressed to daca@rho.co, and its latest message is from an EXTERNAL
sender (not @rho.co). Borrower entity/lender are NOT guessed — intake_email flags the
case for the rep to confirm. The sender domain is only a display fallback for the name.

CREDENTIALS: a Google service account with domain-wide delegation to read daca@rho.co
(`GOOGLE_APPLICATION_CREDENTIALS` + `GMAIL_DELEGATED_USER=daca@rho.co`). Never committed;
local .env / Rhollout Secret Manager. Deferred google import so the app loads without it.
On Rhollout this runs on the scheduled sync; an agent session can instead feed a
snapshot (see tools/seed_register.py --gmail) produced from the Gmail MCP.
"""

from __future__ import annotations
import os

DACA_INBOX = "daca@rho.co"
RHO_DOMAIN = "@rho.co"


class GmailClient:
    def __init__(self, delegated_user=None, inbox=None, credentials_file=None,
                 newer_than="14d", query=None):
        self.delegated_user = delegated_user or os.environ.get("GMAIL_DELEGATED_USER", DACA_INBOX)
        self.inbox = inbox or os.environ.get("DACA_INBOX", DACA_INBOX)
        self.credentials_file = credentials_file or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        self.query = query or f"to:{self.inbox} newer_than:{newer_than} -from:{RHO_DOMAIN}"

    def configured(self) -> bool:
        return bool(self.credentials_file and self.delegated_user)

    def _service(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        ).with_subject(self.delegated_user)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @staticmethod
    def _header(headers: list[dict], name: str) -> str:
        return next((h["value"] for h in headers if h["name"].lower() == name.lower()), "")

    @staticmethod
    def _addr(raw: str) -> tuple[str, str]:
        """'Pooneet Kant <pooneet@x.com>' -> (name, email)."""
        raw = raw.strip()
        if "<" in raw and ">" in raw:
            name = raw.split("<", 1)[0].strip().strip('"')
            email = raw.split("<", 1)[1].split(">", 1)[0].strip()
            return name, email
        return "", raw

    def fetch(self) -> list[dict]:
        """Return net-new DACA inquiry thread dicts for sync_email_intake."""
        if not self.configured():
            raise RuntimeError("Gmail not configured: set GOOGLE_APPLICATION_CREDENTIALS "
                               "and GMAIL_DELEGATED_USER (daca@rho.co).")
        svc = self._service()
        threads = svc.users().threads().list(userId="me", q=self.query, maxResults=50).execute()
        out = []
        for th in threads.get("threads", []):
            full = svc.users().threads().get(userId="me", id=th["id"], format="metadata",
                                             metadataHeaders=["From", "Subject", "Date"]).execute()
            msgs = full.get("messages", [])
            if not msgs:
                continue
            # latest external message drives the intake
            ext = [m for m in msgs
                   if RHO_DOMAIN not in self._header(m.get("payload", {}).get("headers", []), "From")]
            m = (ext or msgs)[-1]
            headers = m.get("payload", {}).get("headers", [])
            name, email = self._addr(self._header(headers, "From"))
            out.append({
                "thread_id": th["id"],
                "requester_email": email,
                "requester_name": name,
                "entity_name": "",  # not inferred — intake flags for confirmation
                "subject": self._header(headers, "Subject"),
                "snippet": m.get("snippet", ""),
                "received_date": None,  # set by intake to now if absent
            })
        return out
