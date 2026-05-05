"""
Google authentication helper — supports two modes:

1. OAuth user credentials (your personal account)
   - Preferred when you can't grant a service account access to all required
     resources, or when reading from your own Gmail inbox
   - Set GOOGLE_OAUTH_CREDENTIALS_PATH and run scripts/google_oauth_setup.py
     to generate token.json

2. Service account with optional domain-wide delegation
   - Used for production / when service account has been granted access
   - Required for impersonating other users (e.g. reading daca@rho.co inbox
     directly via with_subject())

The integration modules call get_credentials(scopes, delegated_user) and the
helper picks the right path based on what's configured.
"""
import json
import logging
import os
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


# Default token storage location (relative to project root)
DEFAULT_TOKEN_PATH = os.path.expanduser("~/.daca_ops_oauth_token.json")
DEFAULT_OAUTH_CREDS_PATH = os.path.expanduser("~/.daca_ops_oauth_credentials.json")


def _oauth_token_path() -> str:
    return os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", DEFAULT_TOKEN_PATH)


def _oauth_creds_path() -> str:
    return os.environ.get("GOOGLE_OAUTH_CREDENTIALS_PATH", DEFAULT_OAUTH_CREDS_PATH)


def has_oauth_user_credentials() -> bool:
    """True if a valid OAuth user token file is available."""
    return os.path.exists(_oauth_token_path())


def has_service_account() -> bool:
    """True if a service account JSON is configured."""
    return bool(settings.google_service_account_json)


def get_credentials(scopes: list[str], delegated_user: str | None = None) -> Any:
    """
    Return a Google API credentials object suitable for the requested scopes.

    Prefers OAuth user credentials when available, falls back to service
    account. If delegated_user is provided AND a service account is being
    used, applies domain-wide delegation. OAuth user credentials always run
    as the authenticated user — delegated_user is ignored in that mode.
    """
    if has_oauth_user_credentials():
        return _load_oauth_credentials(scopes)
    if has_service_account():
        return _load_service_account_credentials(scopes, delegated_user)
    raise RuntimeError(
        "No Google credentials configured. Either run scripts/google_oauth_setup.py "
        "for OAuth user credentials, or set GOOGLE_SERVICE_ACCOUNT_JSON."
    )


def _load_oauth_credentials(scopes: list[str]) -> Any:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_path = _oauth_token_path()
    creds = Credentials.from_authorized_user_file(token_path, scopes)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Persist refreshed token
            with open(token_path, "w") as f:
                f.write(creds.to_json())
        except Exception as exc:
            logger.warning("Failed to refresh OAuth token: %s", exc)

    return creds


def _load_service_account_credentials(scopes: list[str], delegated_user: str | None) -> Any:
    from google.oauth2 import service_account

    creds_info = json.loads(settings.google_service_account_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info, scopes=scopes
    )
    if delegated_user:
        credentials = credentials.with_subject(delegated_user)
    return credentials


def auth_mode() -> str:
    """Return a short string describing which auth mode is active."""
    if has_oauth_user_credentials():
        return "oauth_user"
    if has_service_account():
        return "service_account"
    return "none"
