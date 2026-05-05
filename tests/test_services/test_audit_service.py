"""
Tests for app.services.audit_service — immutable audit log creation and retrieval.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, ActorType
from app.services import audit_service
from tests.factories import (
    create_daca_request,
    create_ops_manual_version,
)


class TestLogEvent:
    """Tests for audit_service.log_event."""

    @pytest.mark.asyncio
    async def test_creates_immutable_entry(self, db: AsyncSession):
        """log_event should create an AuditLog row that is never updated."""
        req = await create_daca_request(db)
        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            daca_request_id=req.id,
            after_state={"status": "Fraud Initial Review"},
            rationale="New DACA request received via email.",
        )

        assert entry.id is not None
        assert entry.entity_type == "DacaRequest"
        assert entry.entity_id == req.id
        assert entry.action == "created"
        assert entry.actor_type == ActorType.HUMAN
        assert entry.actor_id == "operator@rho.co"
        assert entry.daca_request_id == req.id
        assert entry.after_state == {"status": "Fraud Initial Review"}
        assert entry.rationale == "New DACA request received via email."
        assert entry.created_at is not None

    @pytest.mark.asyncio
    async def test_entry_persists_in_db(self, db: AsyncSession):
        """Entry should be queryable from the database after flush."""
        req = await create_daca_request(db)
        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="test_persist",
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            daca_request_id=req.id,
        )

        result = await db.execute(
            select(AuditLog).where(AuditLog.id == entry.id)
        )
        fetched = result.scalar_one()
        assert fetched.action == "test_persist"
        assert fetched.actor_id == "system"

    @pytest.mark.asyncio
    async def test_stores_before_and_after_state(self, db: AsyncSession):
        """log_event should capture both before_state and after_state."""
        req = await create_daca_request(db)
        before = {"priority": "NORMAL"}
        after = {"priority": "HIGH"}

        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="updated",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            daca_request_id=req.id,
            before_state=before,
            after_state=after,
        )

        assert entry.before_state == {"priority": "NORMAL"}
        assert entry.after_state == {"priority": "HIGH"}

    @pytest.mark.asyncio
    async def test_stores_metadata_and_ip(self, db: AsyncSession):
        """Additional metadata and IP address should be recorded."""
        req = await create_daca_request(db)
        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="email_sent",
            actor_type=ActorType.AGENT,
            actor_id="EmailDraftingAgent",
            metadata={"template": "INTRO_KICKOFF"},
            ip_address="10.0.0.42",
        )

        assert entry.metadata_ == {"template": "INTRO_KICKOFF"}
        assert entry.ip_address == "10.0.0.42"

    @pytest.mark.asyncio
    async def test_attaches_ops_manual_version_when_available(self, db: AsyncSession):
        """When an OpsManualVersion with is_current=True exists, it should be attached."""
        version = await create_ops_manual_version(db, is_current=True)
        req = await create_daca_request(db)

        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            include_ops_manual_version=True,
        )

        assert entry.ops_manual_version == version.version_label

    @pytest.mark.asyncio
    async def test_ops_manual_version_is_none_when_unavailable(self, db: AsyncSession):
        """When no current OpsManualVersion exists, field should be None."""
        req = await create_daca_request(db)

        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            include_ops_manual_version=True,
        )

        assert entry.ops_manual_version is None

    @pytest.mark.asyncio
    async def test_skips_ops_manual_lookup_when_flag_false(self, db: AsyncSession):
        """When include_ops_manual_version=False, skip the lookup entirely."""
        await create_ops_manual_version(db, is_current=True)
        req = await create_daca_request(db)

        entry = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            include_ops_manual_version=False,
        )

        assert entry.ops_manual_version is None


class TestLogStatusChange:
    """Tests for audit_service.log_status_change."""

    @pytest.mark.asyncio
    async def test_records_correct_before_after(self, db: AsyncSession):
        """log_status_change should store from_status and to_status correctly."""
        req = await create_daca_request(db)

        entry = await audit_service.log_status_change(
            db,
            daca_request_id=req.id,
            from_status="Fraud Initial Review",
            to_status="Typeform Sent",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            rationale="Fraud review completed, sending Typeform.",
        )

        assert entry.action == "status_change"
        assert entry.before_state == {"status": "Fraud Initial Review"}
        assert entry.after_state == {"status": "Typeform Sent"}
        assert entry.rationale == "Fraud review completed, sending Typeform."
        assert entry.entity_type == "DacaRequest"
        assert entry.entity_id == req.id
        assert entry.daca_request_id == req.id

    @pytest.mark.asyncio
    async def test_status_change_stores_ip(self, db: AsyncSession):
        """IP address should be captured for status changes."""
        req = await create_daca_request(db)

        entry = await audit_service.log_status_change(
            db,
            daca_request_id=req.id,
            from_status="Fraud Initial Review",
            to_status="Typeform Sent",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            ip_address="192.168.1.1",
        )

        assert entry.ip_address == "192.168.1.1"


class TestGetTimeline:
    """Tests for audit_service.get_timeline."""

    @pytest.mark.asyncio
    async def test_returns_chronological_order(self, db: AsyncSession):
        """Timeline entries should be ordered by created_at ascending."""
        req = await create_daca_request(db)

        # Create entries with explicit timestamps to enforce ordering
        entry1 = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            daca_request_id=req.id,
        )
        entry2 = await audit_service.log_status_change(
            db,
            daca_request_id=req.id,
            from_status="Fraud Initial Review",
            to_status="Typeform Sent",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
        )
        entry3 = await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req.id,
            action="email_sent",
            actor_type=ActorType.AGENT,
            actor_id="EmailDraftingAgent",
            daca_request_id=req.id,
        )

        timeline = await audit_service.get_timeline(db, req.id)

        assert len(timeline) == 3
        # Chronological: created_at of first <= second <= third
        assert timeline[0].created_at <= timeline[1].created_at <= timeline[2].created_at
        assert timeline[0].action == "created"
        assert timeline[1].action == "status_change"
        assert timeline[2].action == "email_sent"

    @pytest.mark.asyncio
    async def test_returns_empty_for_nonexistent_request(self, db: AsyncSession):
        """Querying a non-existent request ID returns an empty list."""
        timeline = await audit_service.get_timeline(db, uuid.uuid4())
        assert timeline == []

    @pytest.mark.asyncio
    async def test_respects_limit_and_offset(self, db: AsyncSession):
        """Pagination via limit and offset should work correctly."""
        req = await create_daca_request(db)

        # Create 5 audit entries
        for i in range(5):
            await audit_service.log_event(
                db,
                entity_type="DacaRequest",
                entity_id=req.id,
                action=f"event_{i}",
                actor_type=ActorType.SYSTEM,
                actor_id="system",
                daca_request_id=req.id,
            )

        page1 = await audit_service.get_timeline(db, req.id, limit=2, offset=0)
        page2 = await audit_service.get_timeline(db, req.id, limit=2, offset=2)
        page3 = await audit_service.get_timeline(db, req.id, limit=2, offset=4)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1  # Only 1 remaining

    @pytest.mark.asyncio
    async def test_only_returns_entries_for_given_request(self, db: AsyncSession):
        """Timeline should not leak entries from other DACA requests."""
        req1 = await create_daca_request(db)
        req2 = await create_daca_request(db)

        await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req1.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            daca_request_id=req1.id,
        )
        await audit_service.log_event(
            db,
            entity_type="DacaRequest",
            entity_id=req2.id,
            action="created",
            actor_type=ActorType.HUMAN,
            actor_id="operator@rho.co",
            daca_request_id=req2.id,
        )

        timeline_1 = await audit_service.get_timeline(db, req1.id)
        timeline_2 = await audit_service.get_timeline(db, req2.id)

        assert len(timeline_1) == 1
        assert len(timeline_2) == 1
        assert timeline_1[0].daca_request_id == req1.id
        assert timeline_2[0].daca_request_id == req2.id
