"""
Salesforce source client — read the Account DACA fields via the REST query API.

Returns the same record shape sync_salesforce consumes: {"Name", "Business_ID__c",
"DACA_Status__c", "DACA_Type__c", "DACA_Agreement_Date__c"}. Read-only.

Auth: the simplest deployable path is an access token + instance URL (from a
connected app's OAuth flow — client-credentials or username-password — run out of
band; this client just uses the resulting bearer token). ENV:
  SF_INSTANCE_URL   e.g. https://rho.my.salesforce.com
  SF_ACCESS_TOKEN   OAuth bearer token for a read-only integration user
  SF_API_VERSION    default v60.0
  SF_SOQL           default: the DACA-accounts query
"""

from __future__ import annotations
import os

DEFAULT_SOQL = ("SELECT Name, Business_ID__c, DACA_Status__c, DACA_Type__c, "
                "DACA_Agreement_Date__c FROM Account WHERE DACA_Status__c != null LIMIT 2000")


class SalesforceClient:
    def __init__(self, instance_url=None, access_token=None, api_version=None, soql=None):
        self.instance_url = (instance_url or os.environ.get("SF_INSTANCE_URL", "")).rstrip("/")
        self.access_token = access_token or os.environ.get("SF_ACCESS_TOKEN", "")
        self.api_version = api_version or os.environ.get("SF_API_VERSION", "v60.0")
        self.soql = soql or os.environ.get("SF_SOQL", DEFAULT_SOQL)

    def configured(self) -> bool:
        return bool(self.instance_url and self.access_token)

    def fetch(self) -> list[dict]:
        if not self.configured():
            raise RuntimeError("Salesforce not configured: set SF_INSTANCE_URL and SF_ACCESS_TOKEN.")
        import httpx
        records, url = [], f"{self.instance_url}/services/data/{self.api_version}/query"
        params = {"q": self.soql}
        with httpx.Client(timeout=60, headers={"Authorization": f"Bearer {self.access_token}",
                                               "Accept": "application/json"}) as c:
            while True:
                r = c.get(url, params=params) if params else c.get(url)
                r.raise_for_status()
                body = r.json()
                # strip Salesforce 'attributes' metadata from each record
                for rec in body.get("records", []):
                    rec.pop("attributes", None)
                    records.append(rec)
                nxt = body.get("nextRecordsUrl")
                if body.get("done", True) or not nxt:
                    return records
                url, params = f"{self.instance_url}{nxt}", None
