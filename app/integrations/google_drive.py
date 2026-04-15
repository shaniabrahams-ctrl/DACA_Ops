"""
Google Drive Integration — upload, download, and manage files.

Auth: Service account with access to DACA folders.
Key folders:
  - Client files: 121c4-xohOHgK8J_-vX-I-Mfoc7nTR3mX
  - Ops manual: 1uB1PnEMnGhrrvDzO-jZXnwVYKBfr0I8C
  - Webster reports: 1tlhEB2u3Xn-3chFJ-8l8eb4PS58-SbEP
"""
import io
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
    scopes = ["https://www.googleapis.com/auth/drive"]
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=scopes
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def upload_file(
    file_content: bytes,
    file_name: str,
    mime_type: str,
    folder_id: str,
) -> dict[str, str]:
    """Upload a file to Google Drive. Returns {id, name, webViewLink}."""
    import asyncio
    from googleapiclient.http import MediaIoBaseUpload

    loop = asyncio.get_event_loop()

    def _upload():
        service = _build_service()
        metadata = {"name": file_name, "parents": [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype=mime_type)
        result = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,name,webViewLink")
            .execute()
        )
        return result

    return await loop.run_in_executor(None, _upload)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def download_file(file_id: str) -> bytes:
    """Download a file from Google Drive by ID."""
    import asyncio
    from googleapiclient.http import MediaIoBaseDownload

    loop = asyncio.get_event_loop()

    def _download():
        service = _build_service()
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    return await loop.run_in_executor(None, _download)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def list_folder_files(folder_id: str) -> list[dict[str, Any]]:
    """List all files in a Drive folder."""
    import asyncio

    loop = asyncio.get_event_loop()

    def _list():
        service = _build_service()
        results = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])

    return await loop.run_in_executor(None, _list)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
async def create_folder(name: str, parent_folder_id: str) -> dict[str, str]:
    """Create a new folder inside a parent Drive folder."""
    import asyncio

    loop = asyncio.get_event_loop()

    def _create():
        service = _build_service()
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }
        result = service.files().create(body=metadata, fields="id,name,webViewLink").execute()
        return result

    return await loop.run_in_executor(None, _create)
