"""
Tests for app.services.daca_request_service — DACA request CRUD and business logic.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.agreement import Agreement
from app.models.compliance_package import CompliancePackage
from app.models.audit_log import AuditLog
from app.services import daca_request_service
from tests.factories import create_borrower, create_lender, create_daca_request


class TestCreate:
    """Tests for daca_request_service.create."""

    @pytest.mark.asyncio
    async def test_generates_sequential_external_ref(self, db: AsyncSession):
        """External ref should follow DACA-YYYY-NNNN format with sequential numbering."""
        year = datetime.now(timezone.utc).year

        req1 = await daca_request_service.create(db, actor_id="operator@rho.co")
        req2 = await daca_request_service.create(db, actor_id="operator@rho.co")

        assert req1.external_ref == f"DACA-{year}-0001"
        assert req2.external_ref == f"DACA-{year}-0002"

    @pytest.mark.asyncio
    async def test_external_ref_format(self, db: AsyncSession):
        """External ref must match DACA-YYYY-NNNN pattern."""
        req = await daca_request_service.create(db, actor_id="operator@rho.co")

        year = datetime.now(timezone.utc).year
        assert req.external_ref.startswith(f"DACA-{year}-")
        # Should be 4-digit zero-padded number
        seq_part = req.external_ref.split("-")[-1]
        assert len(seq_part) == 4
        assert seq_part.isdigit()

    @pytest.mark.asyncio
    async def test_creates_empty_compliance_package(self, db: AsyncSession):
        """create() should also create an empty CompliancePackage linked to the request."""
        req = await daca_request_service.create(db, actor_id="operator@rho.co")

        result = await db.execute(
            select(CompliancePackage).where(CompliancePackage.daca_request_id == req.id)
        )
        package = result.scalar_one_or_none()

        assert package is not None
        assert package.daca_request_id == req.id
        assert package.typeform_pdf_attached is False
        assert package.compliance_approved is False
        assert package.webster_approval_status == "NOT_SUBMITTED"

    @pytest.mark.asyncio
    async def test_creates_empty_agreement(self, db: AsyncSession):
        """create() should also create an Agreement shell linked to the request."""
        req = await daca_request_service.create(db, actor_id="operator@rho.co")

        result = await db.execute(
            select(Agreement).where(Agreement.daca_request_id == req.id)
        )
        agreement = result.scalar_one_or_none()

        assert agreement is not None
        assert agreement.daca_request_id == req.id
        assert agreement.template_version == "10.24.25"
        assert agreement.signing_status == "DRAFT"

    @pytest.mark.asyncio
    async def test_initial_status_is_fraud_review(self, db: AsyncSession):
        """New requests should start in Fraud Initial Review status."""
        req = await daca_request_service.create(db, actor_id="operator@rho.co")

        assert req.status == DacaRequestStatus.FRAUD_INITIAL_REVIEW

    @pytest.mark.asyncio
    async def test_creates_audit_log_entry(self, db: AsyncSession):
        """create() should log a 'created' audit entry."""
        req = await daca_request_service.create(
            db,
            actor_id="operator@rho.co",
            ip_address="10.0.0.1",
        )

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.daca_request_id == req.id,
                AuditLog.action == "created",
            )
        )
        log = result.scalar_one_or_none()

        assert log is not None
        assert log.actor_id == "operator@rho.co"
        assert log.after_state["external_ref"] == req.external_ref
        assert log.ip_address == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_create_with_borrower_and_lender(self, db: AsyncSession):
        """Request should be correctly linked to borrower and lender."""
        borrower = await create_borrower(db)
        lender = await create_lender(db)

        req = await daca_request_service.create(
            db,
            actor_id="operator@rho.co",
            borrower_id=borrower.id,
            lender_id=lender.id,
        )

        assert req.borrower_id == borrower.id
        assert req.lender_id == lender.id

    @pytest.mark.asyncio
    async def test_create_with_all_optional_fields(self, db: AsyncSession):
        """All optional parameters should be stored correctly."""
        req = await daca_request_service.create(
            db,
            actor_id="operator@rho.co",
            source_channel="TYPEFORM",
            source_reference="https://typeform.com/r/abc123",
            typeform_token="abc123",
            priority="HIGH",
            account_type_requested="NEW_ACCOUNT",
            assigned_to="shani.abrahams@rho.co",
            metadata={"notes": "VIP client"},
        )

        assert req.source_channel == "TYPEFORM"
        assert req.source_reference == "https://typeform.com/r/abc123"
        assert req.typeform_token == "abc123"
        assert req.priority == "HIGH"
        assert req.account_type_requested == "NEW_ACCOUNT"
        assert req.assigned_to == "shani.abrahams@rho.co"
        assert req.metadata_ == {"notes": "VIP client"}


class TestGetById:
    """Tests for daca_request_service.get_by_id."""

    @pytest.mark.asyncio
    async def test_returns_existing_request(self, db: AsyncSession):
        """Should return the DacaRequest when found."""
        req = await create_daca_request(db)

        fetched = await daca_request_service.get_by_id(db, req.id)

        assert fetched.id == req.id
        assert fetched.external_ref == req.external_ref

    @pytest.mark.asyncio
    async def test_raises_404_for_missing(self, db: AsyncSession):
        """Should raise HTTPException 404 for non-existent ID."""
        with pytest.raises(HTTPException) as exc_info:
            await daca_request_service.get_by_id(db, uuid.uuid4())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestGetByExternalRef:
    """Tests for daca_request_service.get_by_external_ref."""

    @pytest.mark.asyncio
    async def test_returns_by_external_ref(self, db: AsyncSession):
        """Should find a request by its human-readable reference."""
        req = await create_daca_request(db, external_ref="DACA-2026-9999")

        fetched = await daca_request_service.get_by_external_ref(db, "DACA-2026-9999")

        assert fetched.id == req.id

    @pytest.mark.asyncio
    async def test_raises_404_for_missing_ref(self, db: AsyncSession):
        """Should raise HTTPException 404 for non-existent external_ref."""
        with pytest.raises(HTTPException) as exc_info:
            await daca_request_service.get_by_external_ref(db, "DACA-2026-0000")

        assert exc_info.value.status_code == 404


class TestListRequests:
    """Tests for daca_request_service.list_requests."""

    @pytest.mark.asyncio
    async def test_returns_all_requests(self, db: AsyncSession):
        """Without filters, should return all requests."""
        await create_daca_request(db)
        await create_daca_request(db)
        await create_daca_request(db)

        results = await daca_request_service.list_requests(db)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_filters_by_status(self, db: AsyncSession):
        """Should return only requests matching the given status."""
        await create_daca_request(db, status=DacaRequestStatus.FRAUD_INITIAL_REVIEW)
        await create_daca_request(db, status=DacaRequestStatus.TYPEFORM_SENT)
        await create_daca_request(db, status=DacaRequestStatus.TYPEFORM_SENT)

        results = await daca_request_service.list_requests(
            db, status=DacaRequestStatus.TYPEFORM_SENT
        )

        assert len(results) == 2
        assert all(r.status == DacaRequestStatus.TYPEFORM_SENT for r in results)

    @pytest.mark.asyncio
    async def test_filters_by_priority(self, db: AsyncSession):
        """Should return only requests matching the given priority."""
        await create_daca_request(db, priority="NORMAL")
        await create_daca_request(db, priority="HIGH")
        await create_daca_request(db, priority="URGENT")

        results = await daca_request_service.list_requests(db, priority="HIGH")

        assert len(results) == 1
        assert results[0].priority == "HIGH"

    @pytest.mark.asyncio
    async def test_filters_by_assigned_to(self, db: AsyncSession):
        """Should return only requests assigned to the given operator."""
        await create_daca_request(db, assigned_to="shani.abrahams@rho.co")
        await create_daca_request(db, assigned_to="other.operator@rho.co")

        results = await daca_request_service.list_requests(
            db, assigned_to="shani.abrahams@rho.co"
        )

        assert len(results) == 1
        assert results[0].assigned_to == "shani.abrahams@rho.co"

    @pytest.mark.asyncio
    async def test_combined_filters(self, db: AsyncSession):
        """Multiple filters should be AND-ed together."""
        await create_daca_request(
            db,
            status=DacaRequestStatus.TYPEFORM_SENT,
            priority="HIGH",
        )
        await create_daca_request(
            db,
            status=DacaRequestStatus.TYPEFORM_SENT,
            priority="NORMAL",
        )

        results = await daca_request_service.list_requests(
            db,
            status=DacaRequestStatus.TYPEFORM_SENT,
            priority="HIGH",
        )

        assert len(results) == 1
        assert results[0].priority == "HIGH"

    @pytest.mark.asyncio
    async def test_respects_limit(self, db: AsyncSession):
        """Should respect the limit parameter."""
        for _ in range(5):
            await create_daca_request(db)

        results = await daca_request_service.list_requests(db, limit=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_respects_offset(self, db: AsyncSession):
        """Should respect the offset parameter."""
        for _ in range(5):
            await create_daca_request(db)

        all_results = await daca_request_service.list_requests(db, limit=50)
        offset_results = await daca_request_service.list_requests(db, limit=50, offset=3)

        assert len(offset_results) == 2
        assert offset_results[0].id == all_results[3].id

    @pytest.mark.asyncio
    async def test_ordered_by_created_at_desc(self, db: AsyncSession):
        """Results should be ordered by created_at descending (newest first)."""
        req1 = await create_daca_request(db)
        req2 = await create_daca_request(db)
        req3 = await create_daca_request(db)

        results = await daca_request_service.list_requests(db)

        # Most recently created should be first
        assert results[0].id == req3.id
        assert results[-1].id == req1.id


class TestUpdate:
    """Tests for daca_request_service.update."""

    @pytest.mark.asyncio
    async def test_updates_fields(self, db: AsyncSession):
        """Should update the specified fields on the request."""
        req = await create_daca_request(db)

        updated = await daca_request_service.update(
            db,
            request_id=req.id,
            actor_id="operator@rho.co",
            updates={"priority": "HIGH", "assigned_to": "shani.abrahams@rho.co"},
        )

        assert updated.priority == "HIGH"
        assert updated.assigned_to == "shani.abrahams@rho.co"

    @pytest.mark.asyncio
    async def test_creates_audit_log(self, db: AsyncSession):
        """update() should create an audit log with before/after state."""
        req = await create_daca_request(db, priority="NORMAL")

        await daca_request_service.update(
            db,
            request_id=req.id,
            actor_id="operator@rho.co",
            updates={"priority": "URGENT"},
            ip_address="10.0.0.42",
        )

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.daca_request_id == req.id,
                AuditLog.action == "updated",
            )
        )
        log = result.scalar_one()

        assert log.before_state == {"priority": "NORMAL"}
        assert log.after_state == {"priority": "URGENT"}
        assert log.actor_id == "operator@rho.co"
        assert log.ip_address == "10.0.0.42"

    @pytest.mark.asyncio
    async def test_update_raises_404_for_missing(self, db: AsyncSession):
        """Updating a non-existent request should raise HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            await daca_request_service.update(
                db,
                request_id=uuid.uuid4(),
                actor_id="operator@rho.co",
                updates={"priority": "HIGH"},
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_preserves_unchanged_fields(self, db: AsyncSession):
        """Fields not in the updates dict should remain unchanged."""
        req = await create_daca_request(
            db,
            priority="NORMAL",
            source_channel="EMAIL",
        )

        await daca_request_service.update(
            db,
            request_id=req.id,
            actor_id="operator@rho.co",
            updates={"priority": "HIGH"},
        )

        # Re-fetch to verify
        fetched = await daca_request_service.get_by_id(db, req.id)
        assert fetched.priority == "HIGH"
        assert fetched.source_channel == "EMAIL"  # unchanged
