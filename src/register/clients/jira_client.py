"""
Jira source client — fetch CSHELP "DACA Request" tickets via the Atlassian REST API.

Returns the same ticket shape sync_jira consumes: {"key", "fields": {"summary",
"status": {"name"}, "updated", "labels", "assignee", "created"}}. Auth is HTTP basic
with a Jira account email + API token (read-only is sufficient).

ENV:
  JIRA_BASE_URL     default https://rho.atlassian.net
  JIRA_EMAIL        the account the token belongs to
  JIRA_API_TOKEN    an Atlassian API token (id.atlassian.com → API tokens)
  JIRA_JQL          default: project = CSHELP AND issuetype = "DACA Request" ORDER BY updated DESC
"""

from __future__ import annotations
import os

DEFAULT_JQL = 'project = CSHELP AND issuetype = "DACA Request" ORDER BY updated DESC'
FIELDS = ["summary", "status", "created", "updated", "labels", "assignee"]


class JiraClient:
    def __init__(self, base_url=None, email=None, api_token=None, jql=None):
        self.base_url = (base_url or os.environ.get("JIRA_BASE_URL", "https://rho.atlassian.net")).rstrip("/")
        self.email = email or os.environ.get("JIRA_EMAIL", "")
        self.api_token = api_token or os.environ.get("JIRA_API_TOKEN", "")
        self.jql = jql or os.environ.get("JIRA_JQL", DEFAULT_JQL)

    def configured(self) -> bool:
        return bool(self.email and self.api_token)

    def fetch(self) -> list[dict]:
        if not self.configured():
            raise RuntimeError("Jira not configured: set JIRA_EMAIL and JIRA_API_TOKEN.")
        import httpx
        issues, start = [], 0
        with httpx.Client(timeout=60, auth=(self.email, self.api_token),
                          headers={"Accept": "application/json"}) as c:
            while True:
                r = c.get(f"{self.base_url}/rest/api/3/search",
                          params={"jql": self.jql, "fields": ",".join(FIELDS),
                                  "startAt": start, "maxResults": 100})
                r.raise_for_status()
                body = r.json()
                batch = body.get("issues", [])
                issues.extend(batch)
                start += len(batch)
                if start >= body.get("total", 0) or not batch:
                    return issues
