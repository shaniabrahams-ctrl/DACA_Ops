"""
Google Sheets Integration — reads Typeform responses and appends rows.

Key sheets:
  - Typeform responses: 1Oog92OTZ5w4Lss-CSVJ-jos8d4Or3K8qu6EQe0EuvtE (gid: 1055296310)
  - DACA Summary: 140z-O_ZoRyY97w4W5hBYBsUylQPJysj8rVXbzRJzRls
"""
import json
import logging
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)


def _build_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if not settings.google_service_account_json:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON not configured")

    creds_info = json.loads(settings.google_service_account_json)
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=scopes
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def read_range(spreadsheet_id: str, range_name: str) -> list[list[str]]:
    """Read a range from a Google Sheet. Returns rows as list of lists."""
    import asyncio

    loop = asyncio.get_event_loop()

    def _read():
        service = _build_service()
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])

    return await loop.run_in_executor(None, _read)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def append_row(spreadsheet_id: str, range_name: str, values: list[Any]) -> None:
    """Append a row to a Google Sheet."""
    import asyncio

    loop = asyncio.get_event_loop()

    def _append():
        service = _build_service()
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": [values]},
        ).execute()

    await loop.run_in_executor(None, _append)


async def get_typeform_responses_since(last_token: str | None = None) -> list[dict[str, Any]]:
    """
    Read Typeform response rows from the Google Sheet.
    Returns rows as dicts keyed by the Typeform column headers.

    Headers (exact Typeform column names):
      Lender Legal Name, Lender Business Address, How many lender reps,
      Lender Rep 1 Name, Lender Rep 1 Phone, Lender Rep 1 Email,
      Lender Rep 2 Name, Lender Rep 2 Phone, Lender Rep 2 Email,
      Lender Rep 3 Name, Lender Rep 3 Phone, Lender Rep 3 Email,
      Does borrower have a Rho account, Borrower Legal Name,
      Borrower Business Address, Borrower Contact Name, Borrower Contact Email,
      Loan Agreement URL, Referral Source, Government receivables involved,
      Multiple accounts, Preferred transfer method, Additional info, Token, Submitted At
    """
    rows = await read_range(settings.typeform_sheet_id, "A:Z")
    if not rows:
        return []

    headers = rows[0]
    data_rows = rows[1:]

    results = []
    for row in data_rows:
        # Pad row to header length
        padded = row + [""] * (len(headers) - len(row))
        entry = dict(zip(headers, padded))

        # Filter by token if provided (incremental polling)
        if last_token and entry.get("Token", "") <= last_token:
            continue
        results.append(entry)

    return results
