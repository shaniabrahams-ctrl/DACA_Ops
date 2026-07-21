"""
Google Drive writer — file a document into a case's client folder.

Client folders live under `DACA Documents / DACAs {year}` and follow the naming
convention `{Business ID} - {Business Name}` (e.g. "46826 - Bud Financial Inc.").
This writer finds that folder (or creates it), lists what's already there (for
idempotency), and uploads bytes.

CREDENTIALS: a Google service account with write access to the DACA Drive, provided
via `GOOGLE_APPLICATION_CREDENTIALS` (path to the service-account JSON) — never in
git. On Rhollout this comes from Secret Manager. The google-api-python-client import
is deferred so the rest of the app loads without the dependency; a deployment that
uses this writer installs it (see requirements.txt).

NOTE (R12 / MCP boundary): a running FastAPI/Rhollout service cannot call the Drive
MCP tools (those are agent-only). It uses this service-account client instead. When
an agent session does the filing interactively, it can drive the MCP directly; this
class is the deployed path.
"""

from __future__ import annotations
import os
from typing import Optional

# DACA Drive folder IDs (from the DACA Ops Drive; see the gdrive reference).
DACA_YEAR_PARENTS = {
    2026: "1FXjtSGrg4q41NMYYiskQ6-EBAtBa1dXn",
    2025: "1_3htqupyL69sT_m2U7oS_bYxP1ExOhBf",
    2024: "1qSk4czS5fL18qnOHInPwQq4YztLNZMdE",
}
FOLDER_MIME = "application/vnd.google-apps.folder"


def client_folder_name(business_id: Optional[str], entity_name: str, matched: bool) -> str:
    """`{BID} - {Name}` for a matched case; the bare borrower name for an unmatched one."""
    if matched and business_id:
        return f"{business_id} - {entity_name}"
    return entity_name


class GoogleDriveWriter:
    def __init__(self, default_year: int = 2026,
                 year_parents: Optional[dict] = None,
                 holding_parent_id: Optional[str] = None,
                 credentials_file: Optional[str] = None):
        self.default_year = default_year
        self.year_parents = year_parents or DACA_YEAR_PARENTS
        # Unmatched responses land under this parent (defaults to the year folder).
        self.holding_parent_id = holding_parent_id
        self.credentials_file = credentials_file or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        self._svc = None

    def _service(self):
        if self._svc is not None:
            return self._svc
        if not self.credentials_file:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS is not set — a Drive service-account JSON "
                "with write access to the DACA Drive is required to file documents.")
        from google.oauth2 import service_account          # deferred imports
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_file, scopes=["https://www.googleapis.com/auth/drive"])
        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._svc

    def _parent_for(self, matched: bool, year: Optional[int]) -> str:
        if not matched and self.holding_parent_id:
            return self.holding_parent_id
        return self.year_parents[year or self.default_year]

    def _find_child_folder(self, parent_id: str, name: str) -> Optional[str]:
        q = (f"'{parent_id}' in parents and mimeType='{FOLDER_MIME}' "
             f"and name='{self._escape(name)}' and trashed=false")
        res = self._service().files().list(q=q, fields="files(id,name)",
                                           supportsAllDrives=True,
                                           includeItemsFromAllDrives=True).execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def find_or_create_client_folder(self, business_id, entity_name, matched, create_missing,
                                     year: Optional[int] = None):
        name = client_folder_name(business_id, entity_name, matched)
        parent = self._parent_for(matched, year)
        existing = self._find_child_folder(parent, name)
        if existing:
            return existing, name, False
        if not create_missing:
            return None, name, False
        meta = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}
        folder = self._service().files().create(body=meta, fields="id",
                                                 supportsAllDrives=True).execute()
        return folder["id"], name, True

    def list_filenames(self, folder_id: str) -> set:
        q = f"'{folder_id}' in parents and trashed=false"
        names, page = set(), None
        while True:
            res = self._service().files().list(q=q, fields="nextPageToken, files(name)",
                                                pageToken=page, supportsAllDrives=True,
                                                includeItemsFromAllDrives=True).execute()
            names.update(f["name"] for f in res.get("files", []))
            page = res.get("nextPageToken")
            if not page:
                return names

    def upload(self, folder_id: str, filename: str, content_type: str, data: bytes) -> str:
        import io
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=content_type or "application/octet-stream",
                                  resumable=False)
        meta = {"name": filename, "parents": [folder_id]}
        f = self._service().files().create(body=meta, media_body=media,
                                           fields="id, webViewLink",
                                           supportsAllDrives=True).execute()
        return f.get("webViewLink") or f"https://drive.google.com/file/d/{f['id']}/view"

    @staticmethod
    def _escape(name: str) -> str:
        return name.replace("\\", "\\\\").replace("'", "\\'")
