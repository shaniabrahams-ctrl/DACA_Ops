"""
WorkflowOrchestratorAgent — syncs state transitions to external systems.

Triggered on any DacaRequest state transition.
Purely mechanical — no AI decisions.

Actions:
  1. Transition Jira ticket to matching status
  2. Add a Jira comment documenting the transition
  3. Update the DACA Summary Google Sheet row
  4. Escalate after 3 retries on integration failure
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_agent import BaseAgent, AgentResult
from app.models.daca_request import DacaRequest
from app.config import settings

logger = logging.getLogger(__name__)

# Maximum retries before escalating to human review
MAX_RETRIES = 3


class WorkflowOrchestratorAgent(BaseAgent):
    name = "WorkflowOrchestratorAgent"

    async def run(
        self,
        db: AsyncSession,
        daca_request_id: uuid.UUID,
        input_payload: dict[str, Any],
    ) -> AgentResult:
        """
        Sync a state transition to Jira and Google Sheets.

        input_payload: {
            previous_status: str,
            new_status: str,
            actor: str,
            rationale: str | None,
        }
        """
        from app.integrations import jira as jira_integration
        from app.integrations import google_sheets as sheets_integration

        previous_status = input_payload.get("previous_status", "")
        new_status = input_payload.get("new_status", "")
        actor = input_payload.get("actor", "system")
        rationale = input_payload.get("rationale", "")

        # Load the DACA request
        result = await db.execute(
            select(DacaRequest).where(DacaRequest.id == daca_request_id)
        )
        request = result.scalar_one_or_none()
        if request is None:
            return AgentResult(
                success=False,
                output={"error": "DacaRequest not found"},
                confidence=1.0,
            )

        errors: list[str] = []
        jira_synced = False
        sheets_synced = False

        # --- 1. Sync Jira ---
        if request.jira_ticket_key:
            jira_synced = await self._sync_jira(
                jira_key=request.jira_ticket_key,
                new_status=new_status,
                previous_status=previous_status,
                external_ref=request.external_ref,
                actor=actor,
                rationale=rationale,
                errors=errors,
            )

        # --- 2. Sync Google Sheets summary row ---
        sheets_synced = await self._sync_google_sheets(
            external_ref=request.external_ref,
            new_status=new_status,
            actor=actor,
            errors=errors,
        )

        # Update Jira status field on the request record
        if jira_synced:
            request.jira_status = new_status
            await db.flush()

        # Determine outcome
        if errors:
            return AgentResult(
                success=False,
                output={
                    "jira_synced": jira_synced,
                    "sheets_synced": sheets_synced,
                    "errors": errors,
                    "escalation": "Integration sync failed after retries. Manual sync required.",
                },
                confidence=1.0,
                recommendation=(
                    f"External sync failed for {request.external_ref}: {'; '.join(errors)}. "
                    "Operator should manually verify Jira and Google Sheets are up to date."
                ),
            )

        return AgentResult(
            success=True,
            output={
                "jira_synced": jira_synced,
                "sheets_synced": sheets_synced,
                "previous_status": previous_status,
                "new_status": new_status,
            },
            confidence=1.0,
            recommendation=f"Synced transition {previous_status} -> {new_status} to external systems.",
        )

    async def _sync_jira(
        self,
        jira_key: str,
        new_status: str,
        previous_status: str,
        external_ref: str,
        actor: str,
        rationale: str,
        errors: list[str],
    ) -> bool:
        """Transition Jira issue and add a comment. Returns True on success."""
        from app.integrations import jira as jira_integration

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        comment = (
            f"[DACA Ops] Status transitioned: {previous_status} → {new_status}\n"
            f"Actor: {actor}\n"
            f"Time: {now}\n"
        )
        if rationale:
            comment += f"Rationale: {rationale}\n"

        try:
            await jira_integration.transition_issue(jira_key, new_status)
        except Exception as exc:
            msg = f"Jira transition failed for {jira_key}: {exc}"
            logger.error(msg)
            errors.append(msg)
            return False

        try:
            await jira_integration.add_comment(jira_key, comment)
        except Exception as exc:
            # Transition succeeded but comment failed — note but don't fail overall
            msg = f"Jira comment failed for {jira_key}: {exc}"
            logger.warning(msg)
            errors.append(msg)

        return True

    async def _sync_google_sheets(
        self,
        external_ref: str,
        new_status: str,
        actor: str,
        errors: list[str],
    ) -> bool:
        """Update or append a row in the DACA Summary sheet. Returns True on success."""
        from app.integrations import google_sheets as sheets_integration

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        try:
            # Read existing rows to find and update, or append if new
            rows = await sheets_integration.read_range(
                settings.daca_summary_sheet_id, "A:Z"
            )

            # Find the row with matching external_ref (column A)
            row_index = None
            if rows:
                for i, row in enumerate(rows):
                    if row and row[0] == external_ref:
                        row_index = i + 1  # Sheets is 1-indexed
                        break

            if row_index is None:
                # Append a new row: [external_ref, status, last_updated, updated_by]
                await sheets_integration.append_row(
                    settings.daca_summary_sheet_id,
                    "A:D",
                    [external_ref, new_status, now, actor],
                )
            else:
                # Update existing row — write status, timestamp, and actor columns (B, C, D)
                update_range = f"B{row_index}:D{row_index}"
                await self._update_range(
                    settings.daca_summary_sheet_id,
                    update_range,
                    [[new_status, now, actor]],
                )

            return True

        except Exception as exc:
            msg = f"Google Sheets sync failed: {exc}"
            logger.error(msg)
            errors.append(msg)
            return False

    @staticmethod
    async def _update_range(
        spreadsheet_id: str, range_name: str, values: list[list[Any]]
    ) -> None:
        """Update an existing range in a Google Sheet."""
        import asyncio
        from app.integrations.google_sheets import _build_service

        loop = asyncio.get_event_loop()

        def _update():
            service = _build_service()
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            ).execute()

        await loop.run_in_executor(None, _update)
