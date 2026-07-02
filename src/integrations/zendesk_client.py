"""
Zendesk client — the client-facing communication channel for DACA Ops.

Jira/CSHELP tracks the case end-to-end for internal ops (intake -> compliance
-> signing). Zendesk is the separate channel where the client actually writes
in and where the DACA Ops team replies, attaches documents, and shares
SendSafely links. This module talks to Zendesk directly; it does not touch
Jira.

Design is adapted from Rho's existing "Signal" tool's Zendesk integration
(fraud/TM), which got several things right that we keep:
  - Auth header built once, from three env vars, reused across requests.
  - Ticket lookup goes through the general search API, not a dedicated
    org/user endpoint that may need scopes we don't have.
  - Every lookup degrades gracefully (returns None/empty) instead of raising
    — a missing ticket or a failed comment fetch should never block the rest
    of a case investigation.
  - Ticket + comment thread are fetched in parallel.
  - Zendesk macros are surfaced as candidate reply templates.
  - Two dedicated test endpoints (read-only, then a tagged write) to verify
    credentials before touching a real case.

What's different here, and why:
  - DACA Ops has a hard, repo-wide rule: nothing external sends without an
    explicit human approval (see docusign_preparer.py, email_drafter.py).
    This client only implements the write primitive (post_public_comment);
    it never decides content or calls itself. src/agents/client_comms_agent.py
    is the only caller, and it requires an `approved_by` identity on every
    send so the human gate is enforced by the function signature, not by
    convention.
  - Zendesk here is a live, shared, client-facing queue — real clients file
    tickets in the same instance. Signal's write-check pattern (create a
    tagged ticket, eyeball it in the agent view) is fine for an internal
    fraud-tooling instance; here it would leave test noise in a queue
    clients can also see. test_write() below creates the ticket with only
    an internal-only comment (no public comment == not client-visible) and
    tags it, so a stray test run cannot reach a client.
  - Attachments and SendSafely links are first-class here, since they're
    the explicit reason this channel exists for DACA Ops (sending signed
    templates, requesting compliance documents back).
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
from dataclasses import dataclass, field
from typing import Optional


class ZendeskAPIError(Exception):
    """
    Raised on any non-2xx Zendesk response, carrying the real upstream
    status code and body. Callers that sit behind a reverse proxy should
    map this to a 5xx of their own choosing rather than passing the status
    straight through — some proxies intercept specific codes (e.g. 502)
    and replace the body with an HTML error page, which breaks JSON
    parsing on the caller side.
    """

    def __init__(self, status_code: int, body: str, endpoint: str):
        self.status_code = status_code
        self.body = body
        self.endpoint = endpoint
        super().__init__(f"Zendesk API error {status_code} on {endpoint}: {body[:300]}")


@dataclass
class ZendeskTicketData:
    id: str
    url: str
    subject: str
    status: str
    requester_email: str
    tags: list[str] = field(default_factory=list)
    created_at: Optional[str] = None


@dataclass
class ZendeskComment:
    id: str
    author_id: str
    body: str
    public: bool
    created_at: str


@dataclass
class ZendeskTicketThread:
    ticket: ZendeskTicketData
    comments: list[ZendeskComment]


@dataclass
class ZendeskMacro:
    id: str
    title: str
    comment_text: str


@dataclass
class SendReceipt:
    """
    Returned by every send-side call. Nothing in this module keeps its own
    log — the caller (client_comms_agent, and eventually the case register)
    is responsible for persisting receipts. See GUMLOOP_AGENT_REVIEW.md
    Part D: "every action returns a receipt into the append-only event
    log" is the property that made the old Gumloop agents' silent failures
    (fired actions whose completion is unknown) possible to catch.
    """

    ticket_id: str
    action: str                # "public_comment" | "internal_note" | "ticket_created"
    approved_by: str
    comment_id: Optional[str]
    attachment_count: int


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text or "").strip()


def _clean_org_query(name: str) -> str:
    """Strip trailing punctuation clients commonly add to entity names
    ("Acme Corp.", "Anonos, Inc.") before using it as a search term."""
    return name.strip().rstrip(".,").strip()


class ZendeskClient:
    """
    Thin async wrapper over the Zendesk REST API. Holds no case knowledge —
    that lives in client_comms_agent.py, which is the only module that
    should compose replies and decide when to send.
    """

    def __init__(
        self,
        subdomain: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        http_client=None,
    ):
        self.subdomain = subdomain or os.environ["ZENDESK_SUBDOMAIN"]
        email = email or os.environ["ZENDESK_EMAIL"]
        api_token = api_token or os.environ["ZENDESK_API_TOKEN"]

        # The "/token:" separator marks this as an API token, not a password.
        # Omitting it produces a silent 401 rather than a helpful error.
        raw = f"{email}/token:{api_token}"
        self._auth_header = "Basic " + base64.b64encode(raw.encode()).decode()
        self._base_url = f"https://{self.subdomain}.zendesk.com/api/v2"

        # Injected HTTP client (e.g. httpx.AsyncClient) so this module stays
        # testable without a live Zendesk account. Must expose an async
        # `.request(method, url, headers=, json=, params=, content=)`.
        self._http = http_client

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {"Authorization": self._auth_header, **kwargs.pop("headers", {})}
        response = await self._http.request(method, url, headers=headers, **kwargs)
        if response.status_code >= 300:
            raise ZendeskAPIError(response.status_code, response.text, path)
        if not response.content:
            return {}
        return response.json()

    # ---- Lookup (read path — mirrors Signal's org-lookup pattern) ----

    async def find_ticket_for_client(
        self, entity_name: str, requester_email: Optional[str] = None
    ) -> Optional[ZendeskTicketData]:
        """
        Find the most relevant open ticket for a DACA case. Requester email
        is the more precise signal when we have it (from Typeform/Jira);
        entity name is the fallback.

        Matching order: exact requester email -> entity name in subject
        (exact, then substring both directions) -> most recently updated
        result. Returns None on no match or any failure — a case may
        legitimately have no Zendesk ticket yet.
        """
        try:
            if requester_email:
                result = await self._request(
                    "GET",
                    "search.json",
                    params={"query": f"type:ticket requester:{requester_email}", "sort_by": "updated_at"},
                )
                tickets = result.get("results", [])
                if tickets:
                    return self._parse_ticket(tickets[-1])

            query = _clean_org_query(entity_name)
            result = await self._request(
                "GET",
                "search.json",
                params={"query": f'type:ticket "{query}"', "sort_by": "updated_at"},
            )
            tickets = result.get("results", [])
            if not tickets:
                return None

            exact = [t for t in tickets if t.get("subject", "").strip().lower() == query.lower()]
            if exact:
                return self._parse_ticket(exact[0])

            contains = [t for t in tickets if query.lower() in t.get("subject", "").lower()]
            if contains:
                return self._parse_ticket(contains[0])

            return self._parse_ticket(tickets[0])
        except ZendeskAPIError:
            return None

    async def get_ticket_with_thread(self, ticket_id: str) -> Optional[ZendeskTicketThread]:
        """
        Fetch ticket metadata and its full comment thread in parallel.
        Degrades gracefully: if comments fail, the ticket still returns
        with an empty thread rather than erroring out.
        """
        ticket_task = self._request("GET", f"tickets/{ticket_id}.json")
        comments_task = self._request("GET", f"tickets/{ticket_id}/comments.json")

        ticket_result, comments_result = await asyncio.gather(
            ticket_task, comments_task, return_exceptions=True
        )

        if isinstance(ticket_result, Exception):
            return None

        ticket = self._parse_ticket(ticket_result.get("ticket", ticket_result))
        comments = []
        if not isinstance(comments_result, Exception):
            for c in comments_result.get("comments", []):
                comments.append(
                    ZendeskComment(
                        id=str(c.get("id", "")),
                        author_id=str(c.get("author_id", "")),
                        body=c.get("plain_body") or _strip_html(c.get("html_body", "")),
                        public=c.get("public", True),
                        created_at=c.get("created_at", ""),
                    )
                )

        return ZendeskTicketThread(ticket=ticket, comments=comments)

    async def list_macros(self) -> list[ZendeskMacro]:
        """
        Surface active Zendesk macros as candidate reply templates.

        These are NOT the primary source of DACA reply language — the
        macros in src/agents/email_drafter.py (sourced from the Notion SOP)
        are git-versioned and are what generate_reply grounds on. This
        exists to spot drift: if a Zendesk-side macro diverges from the
        git-versioned wording, that's worth surfacing to the DRI rather
        than letting two copies of "the standard reply" quietly disagree
        (the exact failure mode the old Gumloop KB file suffered from).
        """
        try:
            result = await self._request("GET", "macros.json", params={"active": "true", "per_page": 100})
        except ZendeskAPIError:
            return []

        macros = []
        for m in result.get("macros", []):
            comment_action = next(
                (a for a in m.get("actions", []) if a.get("field") in ("comment_value_html", "comment_value")),
                None,
            )
            if not comment_action:
                continue
            macros.append(
                ZendeskMacro(
                    id=str(m.get("id", "")),
                    title=m.get("title", ""),
                    comment_text=_strip_html(comment_action.get("value", "")),
                )
            )
        return macros

    # ---- Write path — dumb primitives only; agent layer owns approval ----

    async def upload_attachment(self, filename: str, file_bytes: bytes, content_type: str) -> str:
        """
        Zendesk requires a two-step attach: upload the bytes to get a token,
        then reference that token in the comment payload. Returns the
        upload token.
        """
        result = await self._request(
            "POST",
            "uploads.json",
            params={"filename": filename},
            headers={"Content-Type": content_type},
            content=file_bytes,
        )
        return result["upload"]["token"]

    async def post_comment(
        self,
        ticket_id: str,
        body: str,
        approved_by: str,
        public: bool = True,
        upload_tokens: Optional[list[str]] = None,
    ) -> SendReceipt:
        """
        Post a comment to a ticket. This is the only function in this
        module that sends anything outward. `approved_by` is required —
        not optional, not defaulted — so a human reviewer identity is
        attached to every outbound message at the type level, not by
        convention. Callers should be exactly one place: client_comms_agent
        .send_reply(), invoked only after a human has reviewed the draft.
        """
        if not approved_by:
            raise ValueError("post_comment requires approved_by — no anonymous sends.")

        comment: dict = {"body": body, "public": public}
        if upload_tokens:
            comment["uploads"] = upload_tokens

        result = await self._request(
            "PUT",
            f"tickets/{ticket_id}.json",
            json={"ticket": {"comment": comment}},
        )
        audits = result.get("audit", {})
        comment_id = None
        for event in audits.get("events", []):
            if event.get("type") == "Comment":
                comment_id = str(event.get("id", ""))
                break

        return SendReceipt(
            ticket_id=str(ticket_id),
            action="public_comment" if public else "internal_note",
            approved_by=approved_by,
            comment_id=comment_id,
            attachment_count=len(upload_tokens or []),
        )

    async def create_ticket(
        self,
        subject: str,
        body: str,
        requester_email: str,
        approved_by: str,
        tags: Optional[list[str]] = None,
        public: bool = True,
    ) -> ZendeskTicketData:
        """Open a new client-facing ticket (rare — most DACA conversations
        arrive as an inbound client ticket rather than one Rho opens)."""
        if not approved_by:
            raise ValueError("create_ticket requires approved_by — no anonymous sends.")

        result = await self._request(
            "POST",
            "tickets.json",
            json={
                "ticket": {
                    "subject": subject,
                    "comment": {"body": body, "public": public},
                    "requester": {"email": requester_email},
                    "tags": tags or [],
                }
            },
        )
        return self._parse_ticket(result["ticket"])

    # ---- Connection tests ----

    async def test_read(self) -> bool:
        """Confirm read credentials work: list 1 ticket. Raises on failure
        so a bad token surfaces immediately rather than as a later 401
        buried in a case investigation."""
        result = await self._request("GET", "tickets.json", params={"per_page": 1})
        return "tickets" in result

    async def test_write(self, owner_email: str) -> ZendeskTicketData:
        """
        Confirm write credentials work by creating a real ticket — but
        with only an internal-only comment (public=False) and assigned to
        the integration owner, not a client. Because Zendesk tickets are
        internal-visibility by default until a public comment is added,
        this can never reach a real client's view. Tag it and clean it up
        (close it) after eyeballing it in the agent view — don't leave
        connection-check tickets sitting in the same queue clients use.
        """
        ticket = await self.create_ticket(
            subject="[connection-check] DACA Ops <> Zendesk",
            body="Automated connection check from DACA Ops. Safe to close.",
            requester_email=owner_email,
            approved_by=owner_email,
            tags=["daca-ops-test", "connection-check"],
            public=False,
        )
        return ticket

    # ---- parsing ----

    def _parse_ticket(self, raw: dict) -> ZendeskTicketData:
        requester = raw.get("via", {}).get("source", {}).get("from", {}) or {}
        return ZendeskTicketData(
            id=str(raw.get("id", "")),
            url=raw.get("url", ""),
            subject=raw.get("subject", ""),
            status=raw.get("status", ""),
            requester_email=raw.get("requester_email") or requester.get("address", ""),
            tags=raw.get("tags", []),
            created_at=raw.get("created_at"),
        )
