"""
Google Sheets source client — read the "Rho DACA Summary" sheet's PRIMARY table and
render it as the pipe-table text sync_gsheet already parses.

sync_gsheet.parse_daca_summary expects the primary Business-ID table as markdown-style
pipe rows (>=15 cells per row, cell[1]=row number, cell[2]=Business ID). The Sheets
API returns raw grid values (and drops trailing empty cells), so this client:
  1. locates the primary header row (has "Business ID" + "Lender Name"),
  2. takes rows until the first fully-empty row (the primary table only — never the
     lower sub-tables like the Webster list, which would otherwise be mis-parsed as
     cases), and
  3. pads every row to the header width and renders `| a | b | ... |`.

ENV:
  GOOGLE_APPLICATION_CREDENTIALS  service-account JSON (Sheets read access)
  DACA_SUMMARY_SHEET_ID           default 140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls
  DACA_SUMMARY_RANGE              default 'A1:N1000'
"""

from __future__ import annotations
import os

DEFAULT_SHEET_ID = "140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls"


class GSheetClient:
    def __init__(self, sheet_id=None, cell_range=None, credentials_file=None):
        self.sheet_id = sheet_id or os.environ.get("DACA_SUMMARY_SHEET_ID", DEFAULT_SHEET_ID)
        self.cell_range = cell_range or os.environ.get("DACA_SUMMARY_RANGE", "A1:N1000")
        self.credentials_file = credentials_file or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    def configured(self) -> bool:
        return bool(self.credentials_file)

    def _values(self) -> list[list]:
        if not self.configured():
            raise RuntimeError("Sheets not configured: set GOOGLE_APPLICATION_CREDENTIALS.")
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_file(
            self.credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        res = svc.spreadsheets().values().get(
            spreadsheetId=self.sheet_id, range=self.cell_range,
            majorDimension="ROWS").execute()
        return res.get("values", [])

    @staticmethod
    def _is_header(row: list) -> bool:
        joined = " | ".join(str(c) for c in row).lower()
        return "business id" in joined and "lender name" in joined

    def fetch(self) -> str:
        rows = self._values()
        # find the primary header, then take rows until the first fully-empty row
        start = next((i for i, r in enumerate(rows) if self._is_header(r)), None)
        if start is None:
            return ""
        header = rows[start]
        width = len(header)
        block = [header]
        for r in rows[start + 1:]:
            if not any(str(c).strip() for c in r):   # blank row → end of primary table
                break
            block.append(r)
        lines = []
        for r in block:
            cells = [str(c) for c in r] + [""] * (width - len(r))
            lines.append("| " + " | ".join(cells[:width]) + " |")
        return "\n".join(lines)
