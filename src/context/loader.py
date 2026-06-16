"""
CaseContextLoader — the mandatory context gate for all DACA Ops agent operations.

DESIGN PRINCIPLE:
  No agent operation (DocuSign prep, status update, version send, weekly report)
  may proceed without first calling load(). This is enforced by the agent harness,
  not by prompt instructions. Prompt rules can be violated under context pressure;
  harness gates cannot.

WHAT IT DOES:
  1. Queries every relevant source (Gmail, Jira, Typeform, Drive) in parallel
  2. Scans all Gmail thread attachments — extracts, downloads, and fingerprints
     every DACA document attached to any email in the case threads
  3. Cross-checks attachment provenance: flags if Rho sent the client their
     own document back, or if no WB revision authors appear in any outbound doc
  4. Builds a structured CaseRecord with full timeline, party manifest,
     document inventory, and sourced facts
  5. Runs all discrepancy checks — flags blockers before any operation proceeds
  6. Returns a DocuSign readiness score and missing-field list

ATTACHMENT SCANNING (ShareFile gap redundancy):
  ShareFile notifications go to whoever uploaded/downloaded — often Sam Davidson.
  If Sam doesn't forward them to daca@rho.co, the version agent loses its
  primary detection path. The attachment scanner provides a second path:
  - Reads what was actually attached to emails between Rho and the client
  - Compares outbound Rho attachments against client-submitted attachments
  - Flags content-equivalent documents even without ShareFile visibility
  This would have caught the Anonos failure via the 6/10 emails alone:
  Shani's attachment to Joseph had the same content as Joseph's 6/1 attachment.

AGENT USAGE PATTERN:
  record = await loader.load(case_id="Anonos Innovations LLC")
  if record.blockers:
      return surface_to_human(record.blockers)
  proceed_with_operation(record)
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Optional

from src.context.record import (
    CaseRecord, Entity, Contact, LenderRecord, DocumentRecord,
    TimelineEvent, JiraTicket, OpenItem, DiscrepancyFlag,
    DocuSignReadiness, Source, SourceType, Severity,
)
from src.context.sources.gmail import build_search_queries, tag_thread, extract_document_events
from src.context.sources.attachment_scanner import (
    extract_attachment_records_from_thread,
    download_and_fingerprint_attachments,
    cross_check_attachments,
)
from src.context.analysis.discrepancies import run_all_checks


class CaseContextLoader:
    """
    Reconstructs the full evidentiary record for a DACA case.

    All source queries run in parallel. Full thread content is fetched
    for any thread above the relevance threshold. Facts are extracted,
    timestamped, and sourced before being assembled into CaseRecord.
    """

    def __init__(self, gmail_client, jira_client, drive_client, typeform_sheet_id: str):
        self.gmail = gmail_client
        self.jira = jira_client
        self.drive = drive_client
        self.typeform_sheet_id = typeform_sheet_id

    async def load(
        self,
        case_id: str,
        entity_names: list[str],
        seed_contact_emails: list[str],
        seed_jira_keys: list[str],
        lender_name: Optional[str] = None,
    ) -> CaseRecord:
        """
        Load full case context from all sources.

        Parameters
        ----------
        case_id : str
            Human-readable case identifier (primary entity name).
        entity_names : list[str]
            All debtor entity names — may be more than one (e.g. Anonos had 3).
        seed_contact_emails : list[str]
            Known contact emails from Typeform or prior knowledge.
        seed_jira_keys : list[str]
            Known Jira ticket keys (LEGALHELP-*, CSHELP-*).
        lender_name : str, optional
            Lender name if already known; triggers lender-specific Gmail queries.
        """
        queries = build_search_queries(
            entity_names=entity_names,
            contact_emails=seed_contact_emails,
            jira_keys=seed_jira_keys,
            lender_name=lender_name,
        )

        # Parallel fetch: Gmail threads, Jira tickets, Typeform rows, Drive docs
        gmail_task = self._load_gmail_threads(queries)
        jira_task = self._load_jira_tickets(seed_jira_keys, entity_names)
        typeform_task = self._load_typeform_responses(entity_names)
        drive_task = self._load_drive_documents(entity_names)

        gmail_threads, jira_tickets, typeform_rows, drive_docs = await asyncio.gather(
            gmail_task, jira_task, typeform_task, drive_task
        )

        # Scan email attachments — second detection path independent of ShareFile
        # notifications. Downloads and fingerprints DACA docs from all thread emails,
        # then cross-checks for outbound = client-submitted matches.
        attachment_flags = await self._scan_thread_attachments(gmail_threads)

        # Extract structured facts from all sources
        timeline = self._build_timeline(gmail_threads, jira_tickets)
        entities = self._extract_entities(entity_names, typeform_rows, gmail_threads)
        contacts = self._extract_contacts(typeform_rows, gmail_threads)
        lender = self._extract_lender(typeform_rows, gmail_threads, lender_name)
        documents = self._extract_documents(drive_docs, gmail_threads)

        # Discover additional Jira keys from Gmail thread subjects
        discovered_keys = self._discover_jira_keys(gmail_threads)
        new_keys = [k for k in discovered_keys if k not in seed_jira_keys]
        if new_keys:
            extra_tickets = await self._load_jira_tickets(new_keys, entity_names)
            jira_tickets.extend(extra_tickets)
            timeline.extend(self._build_timeline([], extra_tickets))

        # Discover additional contacts from email participants
        discovered_contacts = self._discover_contacts_from_email(gmail_threads, contacts)
        contacts.extend(discovered_contacts)

        open_items = self._identify_open_items(entities, contacts, lender, documents, jira_tickets)

        record = CaseRecord(
            case_id=case_id,
            loaded_at=datetime.now(timezone.utc),
            entities=entities,
            lender=lender,
            contacts=contacts,
            timeline=sorted(timeline, key=lambda e: e.date),
            documents=documents,
            jira_tickets=jira_tickets,
            open_items=open_items,
            discrepancy_flags=[],
        )

        # Run structural discrepancy checks
        record.discrepancy_flags = run_all_checks(record)

        # Merge attachment-level version flags — these fire even when ShareFile
        # notifications were not forwarded to daca@rho.co
        record.discrepancy_flags.extend(
            self._attachment_flags_to_discrepancies(attachment_flags)
        )

        # Build DocuSign readiness per entity
        record.docusign_readiness = self._score_docusign_readiness(record)

        return record

    async def _scan_thread_attachments(self, threads: list) -> list[dict]:
        """
        For every thread, extract attachment metadata and download DACA documents.
        Cross-check attachment provenance to detect version mismatches.

        This runs against Gmail thread data we already fetched — no extra
        network requests for the thread list, only for the attachment bytes.
        """
        all_attachment_records = []
        for thread in threads:
            # Convert our internal GmailThread object to the dict shape
            # that extract_attachment_records_from_thread expects
            thread_dict = {
                "id": thread.id,
                "messages": [
                    {
                        "id": m.id,
                        "sender": m.sender,
                        "toRecipients": m.to,
                        "ccRecipients": m.cc,
                        "date": m.date.isoformat(),
                        "attachments": m.attachments if hasattr(m, "attachments") else [],
                    }
                    for m in thread.messages
                ],
            }
            records = extract_attachment_records_from_thread(thread_dict)
            all_attachment_records.extend(records)

        if not all_attachment_records:
            return []

        # Download and fingerprint — parallel fetch of attachment bytes
        fingerprinted = await download_and_fingerprint_attachments(
            all_attachment_records, self.gmail
        )

        # Cross-check provenance
        return cross_check_attachments(fingerprinted)

    def _attachment_flags_to_discrepancies(self, flags: list[dict]) -> list:
        """Convert attachment scanner flag dicts to DiscrepancyFlag objects."""
        from src.context.record import DiscrepancyFlag, DiscrepancyKind, Severity, Source, SourceType
        from datetime import timezone

        discrepancies = []
        for flag in flags:
            kind_map = {
                "rho_sent_client_version_back": DiscrepancyKind.WRONG_DOCUMENT_VERSION,
                "outbound_missing_wb_revisions": DiscrepancyKind.WRONG_DOCUMENT_VERSION,
                "no_wb_doc_in_thread": DiscrepancyKind.MISSING_WB_APPROVAL,
            }
            severity_map = {
                "BLOCKER": Severity.BLOCKER,
                "WARNING": Severity.WARNING,
            }
            kind = kind_map.get(flag.get("kind"), DiscrepancyKind.WRONG_DOCUMENT_VERSION)
            severity = severity_map.get(flag.get("severity", "WARNING"), Severity.WARNING)

            evidence = []
            ev = flag.get("evidence", {})
            for msg_id_key in ["outbound_message_id", "client_submitted_message_id"]:
                if ev.get(msg_id_key):
                    evidence.append(Source(
                        source_type=SourceType.GMAIL,
                        source_id=ev[msg_id_key],
                        date=datetime.now(timezone.utc),
                        excerpt=flag.get("description", "")[:200],
                    ))

            discrepancies.append(DiscrepancyFlag(
                kind=kind,
                severity=severity,
                description=flag.get("description", ""),
                evidence=evidence,
            ))
        return discrepancies

    async def _load_gmail_threads(self, queries: list[str]) -> list:
        """
        Run all search queries and deduplicate by thread ID.
        Fetch full thread content for threads tagged as relevant.
        Threads tagged "wb_sharefile" always get full content — they contain
        the document download logs that are invisible in snippets alone.
        """
        seen_thread_ids: set[str] = set()
        threads = []

        for query in queries:
            results = await self.gmail.search_threads(query=query, page_size=50)
            for thread_summary in results:
                if thread_summary["id"] in seen_thread_ids:
                    continue
                seen_thread_ids.add(thread_summary["id"])
                # Reconstruct a partial thread from search snippet for tagging
                partial = self._thread_from_summary(thread_summary)
                partial.relevance_tags = tag_thread(partial)
                threads.append(partial)

        # Fetch full content for all relevant threads
        full_threads = []
        fetch_tasks = [
            self.gmail.get_thread(thread_id=t.id)
            for t in threads
            # Always fetch full content — snippets miss version events,
            # missing attachments, and internal annotations
        ]
        full_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        for thread, result in zip(threads, full_results):
            if isinstance(result, Exception):
                full_threads.append(thread)   # Fall back to partial
            else:
                full = self._parse_full_thread(result)
                full.relevance_tags = tag_thread(full)
                full_threads.append(full)

        return full_threads

    async def _load_jira_tickets(
        self, ticket_keys: list[str], entity_names: list[str]
    ) -> list[JiraTicket]:
        """Fetch known tickets and search Jira for additional tickets by entity name."""
        tickets = []
        for key in ticket_keys:
            try:
                ticket = await self.jira.get_issue(key)
                tickets.append(self._parse_jira_ticket(ticket))
            except Exception:
                pass
        return tickets

    async def _load_typeform_responses(self, entity_names: list[str]) -> list[dict]:
        """
        Search the Typeform GSheet for rows matching any entity name.

        Searches across all columns — entity names may appear in the
        entity name column, the sub-accounts field, or the Gumloop
        reference input column.
        """
        rows = []
        for name in entity_names:
            found = await self.drive.search_sheet(
                file_id=self.typeform_sheet_id,
                query=name,
            )
            rows.extend(found)
        return rows

    async def _load_drive_documents(self, entity_names: list[str]) -> list[dict]:
        """Search Drive for DACA agreements and redlines for any entity."""
        docs = []
        for name in entity_names:
            found = await self.drive.search_files(
                query=f"fullText contains '{name}' and (name contains 'DACA' or name contains 'Redline')"
            )
            docs.extend(found)
        return docs

    def _discover_jira_keys(self, threads: list) -> list[str]:
        """Extract Jira ticket keys from Gmail subject lines and body text."""
        import re
        keys = set()
        pattern = re.compile(r"\b(LEGALHELP|CSHELP)-\d+\b")
        for thread in threads:
            for msg in thread.messages:
                for match in pattern.finditer(f"{msg.subject} {msg.snippet} {msg.body or ''}"):
                    keys.add(match.group())
        return list(keys)

    def _discover_contacts_from_email(self, threads: list, existing: list[Contact]) -> list[Contact]:
        """
        Find contacts that appear in email threads but are not in Typeform.
        These are typically: opposing counsel, WB legal team, additional lender reps.
        Surfaced in the case record so the agent knows all parties.
        """
        existing_emails = {c.email.lower() for c in existing}
        discovered = []
        rho_domain = "rho.co"
        wb_domain = "websterbank.com"
        for thread in threads:
            for msg in thread.messages:
                for email in [msg.sender] + msg.to + msg.cc:
                    if not email or email.lower() in existing_emails:
                        continue
                    if rho_domain in email or wb_domain in email:
                        continue
                    existing_emails.add(email.lower())
                    discovered.append(Contact(
                        name=email,
                        email=email,
                        role="external_party",
                        sources=[Source(
                            source_type=SourceType.GMAIL,
                            source_id=thread.id,
                            date=msg.date,
                            excerpt=f"Appeared as participant in thread: {thread.subject}",
                        )],
                    ))
        return discovered

    def _identify_open_items(
        self,
        entities: list[Entity],
        contacts: list[Contact],
        lender: Optional[LenderRecord],
        documents: list[DocumentRecord],
        jira_tickets: list[JiraTicket],
    ) -> list[OpenItem]:
        """
        Identify action items that must be resolved before DocuSign.
        These are derived from context gaps, not inferred from nothing.
        """
        items = []

        # Missing signer titles
        for contact in contacts:
            if contact.role in ("debtor_signer", "lender_signer") and not contact.title:
                items.append(OpenItem(
                    description=f"Confirm title for signer {contact.name} ({contact.email})",
                    owner="daca_ops",
                    blocking=True,
                    sources=contact.sources,
                ))

        # Missing account IDs
        for entity in entities:
            if not entity.account_ids:
                items.append(OpenItem(
                    description=f"Add account IDs for {entity.legal_name}",
                    owner="daca_ops",
                    blocking=True,
                    sources=entity.sources,
                ))

        # Entities without WB-approved doc
        approved_names = {d.name for d in documents if d.is_wb_approved}
        for entity in entities:
            if not any(entity.legal_name in n for n in approved_names):
                items.append(OpenItem(
                    description=f"Obtain WB approval for DACA template to be used for {entity.legal_name}",
                    owner="legal",
                    blocking=True,
                    sources=entity.sources,
                ))

        return items

    def _score_docusign_readiness(self, record: CaseRecord) -> list[DocuSignReadiness]:
        """
        For each entity, determine which DocuSign fields are ready and which are missing.
        This becomes the prefill manifest for the DocuSign preparation agent.
        """
        readiness = []
        required_fields = ["legal_name", "address", "signer_name", "signer_email",
                           "signer_title", "account_ids", "lender_name",
                           "lender_address", "lender_signer_name", "lender_signer_email"]

        signer_map = {
            c.email: c for c in record.contacts
            if c.role in ("debtor_signer",)
        }

        for entity in record.entities:
            missing = []
            prefilled = {}

            prefilled["legal_name"] = entity.legal_name
            if not entity.address:
                missing.append("entity_address")
            else:
                prefilled["address"] = entity.address

            signer = signer_map.get(next(
                (c.email for c in record.contacts if c.role == "debtor_signer"), ""
            ))
            if signer:
                prefilled["signer_name"] = signer.name
                prefilled["signer_email"] = signer.email
                if not signer.title:
                    missing.append("signer_title")
                else:
                    prefilled["signer_title"] = signer.title
            else:
                missing.extend(["signer_name", "signer_email", "signer_title"])

            if not entity.account_ids:
                missing.append("account_ids")
            else:
                prefilled["account_ids"] = entity.account_ids

            if record.lender:
                prefilled["lender_name"] = record.lender.legal_name
                if record.lender.address:
                    prefilled["lender_address"] = record.lender.address
                else:
                    missing.append("lender_address")
                lender_signer = next(
                    (c for c in record.lender.contacts if c.role == "lender_signer"), None
                )
                if lender_signer:
                    prefilled["lender_signer_name"] = lender_signer.name
                    prefilled["lender_signer_email"] = lender_signer.email
                    if lender_signer.title:
                        prefilled["lender_signer_title"] = lender_signer.title
                    else:
                        missing.append("lender_signer_title")
                else:
                    missing.extend(["lender_signer_name", "lender_signer_email"])
            else:
                missing.extend(["lender_name", "lender_address", "lender_signer_name",
                                "lender_signer_email"])

            readiness.append(DocuSignReadiness(
                entity=entity,
                ready=len(missing) == 0 and not record.blockers,
                missing_fields=missing,
                prefilled=prefilled,
            ))

        return readiness

    # --- Parsing helpers (implement against actual MCP response shapes) ---

    def _thread_from_summary(self, summary: dict):
        from src.context.sources.gmail import GmailThread, GmailMessage
        messages = []
        for m in summary.get("messages", []):
            messages.append(GmailMessage(
                id=m.get("id", ""),
                thread_id=summary.get("id", ""),
                date=self._parse_date(m.get("date", "")),
                sender=m.get("sender", ""),
                to=m.get("toRecipients", []),
                cc=m.get("ccRecipients", []),
                subject=m.get("subject", ""),
                snippet=m.get("snippet", ""),
            ))
        return GmailThread(
            id=summary.get("id", ""),
            subject=messages[0].subject if messages else "",
            messages=messages,
            relevance_tags=[],
        )

    def _parse_full_thread(self, result: dict):
        from src.context.sources.gmail import GmailThread, GmailMessage
        messages = []
        for m in result.get("messages", []):
            # Extract attachment metadata from FULL_CONTENT response
            # Gmail MCP returns attachment_ids; we normalize to the shape
            # attachment_scanner expects: [{attachmentId, filename, mimeType, size}]
            raw_attachments = m.get("attachments") or []
            if not raw_attachments and m.get("attachment_ids"):
                # Older response shape: just a list of IDs, no metadata
                raw_attachments = [{"attachmentId": aid} for aid in m["attachment_ids"]]

            messages.append(GmailMessage(
                id=m.get("id", ""),
                thread_id=result.get("id", ""),
                date=self._parse_date(m.get("date", "")),
                sender=m.get("sender", ""),
                to=m.get("toRecipients", []),
                cc=m.get("ccRecipients", []),
                subject=m.get("subject", ""),
                snippet=m.get("snippet", ""),
                body=m.get("plaintextBody"),
                attachments=raw_attachments,
            ))
        return GmailThread(
            id=result.get("id", ""),
            subject=messages[0].subject if messages else "",
            messages=messages,
            relevance_tags=[],
        )

    def _parse_jira_ticket(self, raw: dict) -> JiraTicket:
        return JiraTicket(
            key=raw.get("key", ""),
            summary=raw.get("fields", {}).get("summary", ""),
            status=raw.get("fields", {}).get("status", {}).get("name", ""),
            created=self._parse_date(raw.get("fields", {}).get("created", "")),
        )

    def _build_timeline(self, threads: list, tickets: list[JiraTicket]) -> list[TimelineEvent]:
        events = []
        for thread in threads:
            for msg in thread.messages:
                events.append(TimelineEvent(
                    date=msg.date,
                    actor=msg.sender,
                    description=f"{msg.subject}: {msg.snippet[:120]}",
                    source=Source(
                        source_type=SourceType.GMAIL,
                        source_id=thread.id,
                        date=msg.date,
                        excerpt=msg.snippet[:200],
                    ),
                    tags=thread.relevance_tags,
                ))
        for ticket in tickets:
            for event in ticket.events:
                events.append(event)
        return events

    def _extract_entities(self, names: list[str], typeform_rows: list[dict], threads: list) -> list[Entity]:
        entities = []
        for name in names:
            matching_rows = [r for r in typeform_rows if name.lower() in str(r).lower()]
            address = None
            for row in matching_rows:
                addr = row.get("address") or row.get("business_address")
                if addr:
                    address = addr
                    break
            entities.append(Entity(
                legal_name=name,
                address=address,
                sources=[
                    Source(
                        source_type=SourceType.TYPEFORM,
                        source_id="typeform_sheet",
                        date=datetime.now(timezone.utc),
                        excerpt=f"Found {len(matching_rows)} Typeform row(s) for {name}",
                    )
                ] if matching_rows else [],
            ))
        return entities

    def _extract_contacts(self, typeform_rows: list[dict], threads: list) -> list[Contact]:
        contacts = []
        seen = set()
        for row in typeform_rows:
            email = row.get("signer_email") or row.get("contact_email")
            if email and email not in seen:
                seen.add(email)
                contacts.append(Contact(
                    name=row.get("signer_name") or row.get("contact_name") or email,
                    email=email,
                    role="debtor_signer",
                    title=row.get("signer_title"),
                    phone=row.get("signer_phone"),
                    sources=[Source(
                        source_type=SourceType.TYPEFORM,
                        source_id="typeform_sheet",
                        date=datetime.now(timezone.utc),
                        excerpt=f"Typeform response for {email}",
                    )],
                ))
        return contacts

    def _extract_lender(
        self,
        typeform_rows: list[dict],
        threads: list,
        known_name: Optional[str],
    ) -> Optional[LenderRecord]:
        for row in typeform_rows:
            lender_name = row.get("lender_name") or row.get("secured_party_name") or known_name
            if lender_name:
                return LenderRecord(
                    legal_name=lender_name,
                    address=row.get("lender_address"),
                    contacts=[
                        Contact(
                            name=row.get("lender_rep_name", ""),
                            email=row.get("lender_rep_email", ""),
                            role="lender_signer",
                            title=row.get("lender_rep_title"),
                            phone=row.get("lender_rep_phone"),
                        )
                    ] if row.get("lender_rep_email") else [],
                    transfer_method=row.get("transfer_method"),
                    sources=[Source(
                        source_type=SourceType.TYPEFORM,
                        source_id="typeform_sheet",
                        date=datetime.now(timezone.utc),
                        excerpt=f"Lender: {lender_name}",
                    )],
                )
        if known_name:
            return LenderRecord(legal_name=known_name)
        return None

    def _extract_documents(self, drive_docs: list[dict], threads: list) -> list[DocumentRecord]:
        docs = []
        for d in drive_docs:
            name = d.get("name", "")
            is_wb = "WB redline" in name or "wb redline" in name.lower()
            docs.append(DocumentRecord(
                name=name,
                drive_id=d.get("id"),
                version_label="v2-wb-counter-redline" if is_wb else "v1-client-redline",
                is_wb_approved=is_wb,
                uploaded_at=self._parse_date(d.get("modifiedTime", "")),
                uploaded_by=d.get("lastModifyingUser", {}).get("emailAddress"),
                sources=[Source(
                    source_type=SourceType.DRIVE,
                    source_id=d.get("id", ""),
                    date=self._parse_date(d.get("modifiedTime", "")),
                    excerpt=f"Drive file: {name}",
                )],
            ))
        return docs

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)
