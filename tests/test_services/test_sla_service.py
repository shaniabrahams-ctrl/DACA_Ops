"""
Tests for app.services.sla_service — SLA status calculation and reporting.

Note: SQLite (used for tests) does not preserve timezone info on datetime columns.
The get_sla_report function calls ``datetime.now(timezone.utc)`` for *now*, but
``created_at`` loaded from SQLite is tz-naive.  We monkeypatch the sla_service
module's ``datetime`` so that ``datetime.now(tz)`` returns a tz-naive result,
matching the SQLite behaviour.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daca_request import DacaRequestStatus
from app.services.sla_service import calculate_sla_status, get_sla_report, SLAStatus
from app.services import sla_service as _sla_mod
from tests.factories import create_daca_request


def _naive_utcnow() -> datetime:
    """Return current UTC time as a naive datetime (matches SQLite storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture()
def patch_sla_datetime(monkeypatch):
    """
    SQLite strips timezone info from stored datetimes but
    ``sla_service.get_sla_report`` creates a tz-aware *now*.  Patch the
    module-level ``datetime`` so ``datetime.now(tz)`` returns a naive UTC
    timestamp, keeping everything consistent for test assertions.

    Apply explicitly via ``@pytest.mark.usefixtures("patch_sla_datetime")``.
    """
    _real_datetime = datetime

    class _NaiveDatetime(_real_datetime):
        @classmethod
        def now(cls, tz=None):
            return _real_datetime.now(timezone.utc).replace(tzinfo=None)

    monkeypatch.setattr(_sla_mod, "datetime", _NaiveDatetime)


class TestCalculateSlaStatus:
    """Tests for the pure function calculate_sla_status."""

    def test_no_sla_deadline_returns_no_sla(self):
        """When sla_deadline is None, status should be NO_SLA."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        result = calculate_sla_status(sla_deadline=None, created_at=created)

        assert result["status"] == SLAStatus.NO_SLA
        assert result["pct_elapsed"] is None
        assert result["hours_remaining"] is None
        assert result["deadline"] is None

    def test_on_track_when_under_80_percent(self):
        """Status should be ON_TRACK when less than 80% of SLA elapsed."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=10)
        # 50% elapsed (5 hours into a 10-hour window)
        now = created + timedelta(hours=5)

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.ON_TRACK
        assert result["pct_elapsed"] == 50.0
        assert result["hours_remaining"] == 5.0

    def test_warning_at_exactly_80_percent(self):
        """Status should be WARNING at exactly 80% elapsed."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=10)
        # Exactly 80% elapsed (8 hours into 10-hour window)
        now = created + timedelta(hours=8)

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.WARNING
        assert result["pct_elapsed"] == 80.0
        assert result["hours_remaining"] == 2.0

    def test_warning_between_80_and_100_percent(self):
        """Status should be WARNING between 80% and 100% elapsed."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=10)
        # 90% elapsed
        now = created + timedelta(hours=9)

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.WARNING
        assert result["pct_elapsed"] == 90.0
        assert result["hours_remaining"] == 1.0

    def test_critical_at_exactly_100_percent(self):
        """Status should be CRITICAL at 100% elapsed (deadline reached)."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=10)
        now = deadline  # Exactly at deadline

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.CRITICAL
        assert result["pct_elapsed"] == 100.0
        assert result["hours_remaining"] == 0.0

    def test_critical_past_deadline(self):
        """Status should be CRITICAL after the deadline has passed."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=10)
        # 2 hours past deadline
        now = deadline + timedelta(hours=2)

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.CRITICAL
        # pct_elapsed is capped at 100.0
        assert result["pct_elapsed"] == 100.0
        assert result["hours_remaining"] == -2.0

    def test_zero_total_hours_returns_critical(self):
        """Edge case: when deadline == created_at, should be CRITICAL."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created  # Zero-length SLA window
        now = created + timedelta(minutes=1)

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.CRITICAL
        assert result["pct_elapsed"] == 100.0

    def test_deadline_in_iso_format(self):
        """The deadline field should be returned as an ISO-format string."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=10)
        now = created + timedelta(hours=1)

        result = calculate_sla_status(deadline, created, now)

        assert result["deadline"] == deadline.isoformat()

    def test_uses_current_utc_when_now_not_provided(self):
        """When now is not passed, calculate_sla_status uses datetime.now(UTC)."""
        created = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
        # Deadline far in the past => always CRITICAL
        deadline = datetime(2020, 1, 2, 0, 0, tzinfo=timezone.utc)

        result = calculate_sla_status(deadline, created)

        assert result["status"] == SLAStatus.CRITICAL

    def test_just_under_80_percent_is_on_track(self):
        """At 79.9% elapsed, status should still be ON_TRACK."""
        created = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
        deadline = created + timedelta(hours=100)
        # 79.9 hours into 100-hour window = 79.9%
        now = created + timedelta(hours=79.9)

        result = calculate_sla_status(deadline, created, now)

        assert result["status"] == SLAStatus.ON_TRACK
        assert result["pct_elapsed"] == 79.9


@pytest.mark.usefixtures("patch_sla_datetime")
class TestGetSlaReport:
    """Tests for get_sla_report which aggregates SLA stats across active requests."""

    @pytest.mark.asyncio
    async def test_empty_database_returns_100_percent_compliance(self, db: AsyncSession):
        """No active requests means 100% compliance."""
        report = await get_sla_report(db)

        assert report["total_active"] == 0
        assert report["compliance_pct"] == 100.0
        assert report["breaches"] == []

    @pytest.mark.asyncio
    async def test_counts_on_track_requests(self, db: AsyncSession):
        """Requests well within SLA should count as on_track."""
        now = _naive_utcnow()
        await create_daca_request(
            db,
            status=DacaRequestStatus.TYPEFORM_SENT,
            sla_deadline=now + timedelta(hours=24),
        )

        report = await get_sla_report(db)

        assert report["total_active"] == 1
        assert report["on_track"] == 1
        assert report["warning"] == 0
        assert report["critical"] == 0

    @pytest.mark.asyncio
    async def test_counts_critical_breaches(self, db: AsyncSession):
        """Requests past their SLA deadline should appear as critical breaches."""
        now = _naive_utcnow()
        await create_daca_request(
            db,
            status=DacaRequestStatus.PENDING_COMPLIANCE_ASSEMBLY,
            sla_deadline=now - timedelta(hours=5),
        )

        report = await get_sla_report(db)

        assert report["total_active"] == 1
        assert report["critical"] == 1
        assert len(report["breaches"]) == 1
        assert report["breaches"][0]["status"] == DacaRequestStatus.PENDING_COMPLIANCE_ASSEMBLY

    @pytest.mark.asyncio
    async def test_excludes_done_terminated_cancelled(self, db: AsyncSession):
        """Requests in DONE, TERMINATED, or CANCELLED should not be included."""
        now = _naive_utcnow()
        for status in [DacaRequestStatus.DONE, DacaRequestStatus.TERMINATED, DacaRequestStatus.CANCELLED]:
            await create_daca_request(
                db,
                status=status,
                sla_deadline=now - timedelta(hours=10),
            )

        report = await get_sla_report(db)

        assert report["total_active"] == 0

    @pytest.mark.asyncio
    async def test_no_sla_requests_counted_separately(self, db: AsyncSession):
        """Requests without SLA deadlines count as no_sla."""
        await create_daca_request(
            db,
            status=DacaRequestStatus.FRAUD_INITIAL_REVIEW,
            sla_deadline=None,
        )

        report = await get_sla_report(db)

        assert report["total_active"] == 1
        assert report["no_sla"] == 1
        # no_sla requests are not counted as compliant in the numerator
        assert report["compliance_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_mixed_statuses_aggregated_correctly(self, db: AsyncSession):
        """Report should correctly aggregate a mix of SLA states."""
        now = _naive_utcnow()

        # ON_TRACK: SLA deadline far in the future
        await create_daca_request(
            db,
            status=DacaRequestStatus.TYPEFORM_SENT,
            sla_deadline=now + timedelta(hours=48),
        )

        # WARNING: SLA 85% elapsed (deadline close)
        await create_daca_request(
            db,
            status=DacaRequestStatus.DOCUSIGN_SENT,
            sla_deadline=now + timedelta(hours=3),
        )

        # CRITICAL: past deadline
        await create_daca_request(
            db,
            status=DacaRequestStatus.PRE_WEBSTER_REVIEW,
            sla_deadline=now - timedelta(hours=2),
        )

        # NO_SLA
        await create_daca_request(
            db,
            status=DacaRequestStatus.LEGAL_REDLINE_REVIEW,
        )

        report = await get_sla_report(db)

        assert report["total_active"] == 4
        assert report["on_track"] >= 1
        assert report["critical"] >= 1
        assert report["no_sla"] >= 1
        assert len(report["breaches"]) >= 1

    @pytest.mark.asyncio
    async def test_compliance_percentage_calculation(self, db: AsyncSession):
        """compliance_pct = (on_track + warning) / total * 100."""
        now = _naive_utcnow()

        # 2 on_track
        for _ in range(2):
            await create_daca_request(
                db,
                status=DacaRequestStatus.TYPEFORM_SENT,
                sla_deadline=now + timedelta(hours=48),
            )

        # 1 critical
        await create_daca_request(
            db,
            status=DacaRequestStatus.DOCUSIGN_SENT,
            sla_deadline=now - timedelta(hours=5),
        )

        report = await get_sla_report(db)

        # 2 compliant out of 3 total = 66.7%
        assert report["total_active"] == 3
        assert report["compliance_pct"] == pytest.approx(66.7, abs=0.1)
