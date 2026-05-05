"""
One-time OAuth user authorization for Google APIs.

Run once: python -m scripts.google_oauth_setup

What it does:
  1. Reads OAuth client credentials from ~/.daca_ops_oauth_credentials.json
     (created in Google Cloud Console as a "Desktop app" OAuth client)
  2. Opens your browser, you sign in with shani.abrahams@rho.co
  3. Saves a refreshable token to ~/.daca_ops_oauth_token.json

After that, the app uses the saved token automatically. No more interactive
sign-ins needed unless the token is revoked.
"""
import os
import sys

OAUTH_CREDS_PATH = os.path.expanduser(
    os.environ.get("GOOGLE_OAUTH_CREDENTIALS_PATH", "~/.daca_ops_oauth_credentials.json")
)
OAUTH_TOKEN_PATH = os.path.expanduser(
    os.environ.get("GOOGLE_OAUTH_TOKEN_PATH", "~/.daca_ops_oauth_token.json")
)

# Scopes covering all three integrations (Sheets, Drive, Gmail)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",
]


def main() -> int:
    if not os.path.exists(OAUTH_CREDS_PATH):
        print(f"ERROR: OAuth credentials file not found at: {OAUTH_CREDS_PATH}")
        print()
        print("Create one in Google Cloud Console:")
        print("  1. https://console.cloud.google.com/apis/credentials?project=daca-ops")
        print("  2. Click '+ CREATE CREDENTIALS' → 'OAuth client ID'")
        print("  3. If asked, configure the OAuth consent screen first:")
        print("     - User type: Internal")
        print("     - App name: DACA Ops Local")
        print("     - Support email + Developer email: your email")
        print("     - Scopes: leave default")
        print("  4. Application type: 'Desktop app'")
        print("  5. Name: 'DACA Ops Local Setup'")
        print("  6. After creating, click 'Download JSON'")
        print(f"  7. Save the downloaded file to: {OAUTH_CREDS_PATH}")
        print()
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib")
        return 1

    print(f"Using OAuth client credentials from: {OAUTH_CREDS_PATH}")
    print(f"Will save token to: {OAUTH_TOKEN_PATH}")
    print()
    print("Your browser will open. Sign in as shani.abrahams@rho.co")
    print("and grant the requested permissions.")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDS_PATH, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    with open(OAUTH_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print()
    print(f"Success — token saved to {OAUTH_TOKEN_PATH}")
    print(f"Authenticated user: {creds.id_token.get('email') if creds.id_token else '(unknown)'}")
    print()
    print("You can now restart the DACA Ops server and Google integrations will work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
