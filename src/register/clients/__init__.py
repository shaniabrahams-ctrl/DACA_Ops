"""
Live source clients for R12 (in-app / scheduled sync).

Each client fetches from a real system of record and returns the EXACT record shape
the matching sync_* function already consumes, so sync_gsheet / sync_jira /
sync_salesforce are unchanged:

  JiraClient.fetch()        -> list[ticket dict]   (key, fields{summary,status{name},updated,...})
  SalesforceClient.fetch()  -> list[record dict]   (Name, Business_ID__c, DACA_Status__c, ...)
  GSheetClient.fetch()      -> str                 (the DACA Summary sheet as pipe-table text)

Credentials come from the environment (local .env / Rhollout Secret Manager), never
git. A client raises a clear error naming the missing variable rather than failing
silently. MCP tools are agent-only, so a deployed service uses these HTTP/service-
account clients — never the MCP connectors.
"""
