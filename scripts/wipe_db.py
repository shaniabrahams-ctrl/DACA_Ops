"""
Wipe the local SQLite database. The app will re-create empty tables on next
startup, and integrations (Jira, Sheets, Gmail, Zendesk) will repopulate
with real data.

Usage: python -m scripts.wipe_db
"""
import os
from app.config import settings


def wipe():
    if not settings.database_url.startswith("sqlite"):
        raise RuntimeError(
            f"Refusing to wipe non-SQLite database: {settings.database_url}. "
            "This script is only for local SQLite dev databases."
        )

    # Extract path from sqlite+aiosqlite:///./daca_ops.db
    path = settings.database_url.split("///")[-1]
    if path.startswith("./"):
        path = path[2:]

    if os.path.exists(path):
        os.remove(path)
        print(f"Wiped local database: {path}")
    else:
        print(f"No database file found at {path} (already wiped)")


if __name__ == "__main__":
    wipe()
