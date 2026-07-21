"""
Typeform API client — download files uploaded through the DACA application form.

The "Please upload your loan agreement" field stores each file behind a private URL
(`https://api.typeform.com/responses/files/<hash>/<name>`). That URL is only
retrievable with a Typeform API token (a Personal Access Token with the
`responses:read` scope, from a user on the DACA form's Typeform workspace), sent as
`Authorization: Bearer <token>`. There is no public/anonymous access.

CREDENTIALS (never in git — daca-data-security skill): the token comes from the
environment (`TYPEFORM_TOKEN`). Locally put it in a gitignored `.env`; on Rhollout
inject it from Secret Manager. If it is absent, download() raises a clear error
rather than silently doing nothing — the caller surfaces that to a human.
"""

from __future__ import annotations
import os
import re
from typing import Optional


class TypeformAuthError(RuntimeError):
    pass


class TypeformClient:
    """Thin pass-through to Typeform's file endpoint. Holds no state beyond the token;
    caches nothing to disk (the bytes are RESTRICTED-tier and must not be persisted)."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("TYPEFORM_TOKEN") or ""

    def _require_token(self) -> str:
        if not self.token:
            raise TypeformAuthError(
                "TYPEFORM_TOKEN is not set. Generate a Personal Access Token with the "
                "'responses:read' scope from admin.typeform.com/account (Personal tokens) "
                "on the DACA form's workspace, and set TYPEFORM_TOKEN (local .env / Rhollout secret).")
        return self.token

    def download(self, url: str) -> tuple[str, str, bytes]:
        """GET the file. Returns (filename, content_type, data). Raises on auth/HTTP error."""
        import httpx  # local import so the module loads without httpx present
        token = self._require_token()
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code in (401, 403):
            raise TypeformAuthError(
                f"Typeform rejected the token ({resp.status_code}) for {url!r}. The token "
                "must belong to a user with access to this form's responses.")
        resp.raise_for_status()
        return self._filename(url, resp.headers.get("content-disposition", "")), \
            resp.headers.get("content-type", "application/octet-stream"), resp.content

    @staticmethod
    def _filename(url: str, content_disposition: str) -> str:
        # Prefer the server-provided name; fall back to the last URL path segment.
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition or "")
        name = m.group(1) if m else url.rstrip("/").rsplit("/", 1)[-1]
        name = name.strip().lstrip("_")            # Typeform prefixes an underscore
        return name or "loan_agreement"
