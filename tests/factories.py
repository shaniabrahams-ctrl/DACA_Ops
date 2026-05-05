"""
Test factories — async helper functions that create model instances with realistic defaults.

Usage:
    borrower = await create_borrower(db)
    borrower = await create_borrower(db, legal_name="Acme Corp")
"""
import uuid
from datetime import datetime, timezone, timedelta

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.borrower import Borrower
from app.models.lender import Lender
from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.agreement import Agreement
from app.models.compliance_package import CompliancePackage
from app.models.account import Account
from app.models.trigger_event import TriggerEvent
from app.models.email_thread import EmailThread
from app.models.email_draft import EmailDraft
from app.models.human_review import HumanReviewItem
from app.models.audit_log import AuditLog, ActorType
from app.models.oversight_config import OversightConfig, OversightMode
from app.models.ops_manual_version import OpsManualVersion

fake = Faker()

# Monotonically increasing sequence for external_ref uniqueness within a test session.
_sequence_counter = 0


def _next_seq() -> int:
    global _sequence_counter
    _sequence_counter += 1
    return _sequence_counter


# ---------------------------------------------------------------------------
# Borrower
# ---------------------------------------------------------------------------

async def create_borrower(db: AsyncSession, **overrides) -> Borrower:
    defaults = {
        "rho_id": str(fake.unique.random_int(min=1000, max=9999)),
        "legal_name": fake.company(),
        "dba_name": fake.company_suffix() + " " + fake.last_name(),
        "entity_type": fake.random_element(["LLC", "CORP", "LP", "INC"]),
        "state_of_formation": fake.state_abbr(),
        "address": {
            "street": fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip": fake.zipcode(),
            "country": "US",
        },
        "primary_contact_name": fake.name(),
        "primary_contact_email": fake.email(),
        "primary_contact_phone": fake.phone_number(),
        "salesforce_account_id": f"001{fake.bothify(text='??########')}",
        "has_rho_account": True,
        "kyb_status": "VERIFIED",
    }
    defaults.update(overrides)
    borrower = Borrower(**defaults)
    db.add(borrower)
    await db.flush()
    return borrower


# ---------------------------------------------------------------------------
# Lender
# ---------------------------------------------------------------------------

async def create_lender(db: AsyncSession, **overrides) -> Lender:
    defaults = {
        "institution_name": fake.company() + " Capital",
        "business_address": fake.address(),
        "rep_count": fake.random_int(min=1, max=3),
        "representatives": [
            {
                "name": fake.name(),
                "phone": fake.phone_number(),
                "email": fake.email(),
            }
        ],
        "primary_contact_email": fake.email(),
        "primary_contact_phone": fake.phone_number(),
        "daca_type": "SPRINGING",
    }
    defaults.update(overrides)
    lender = Lender(**defaults)
    db.add(lender)
    await db.flush()
    return lender


# ---------------------------------------------------------------------------
# DacaRequest
# ---------------------------------------------------------------------------

async def create_daca_request(
    db: AsyncSession,
    *,
    borrower: Borrower | None = None,
    lender: Lender | None = None,
    **overrides,
) -> DacaRequest:
    seq = _next_seq()
    defaults = {
        "external_ref": f"DACA-2026-{seq:04d}",
        "status": DacaRequestStatus.FRAUD_INITIAL_REVIEW,
        "priority": "NORMAL",
        "source_channel": "EMAIL",
        "borrower_id": borrower.id if borrower else None,
        "lender_id": lender.id if lender else None,
    }
    defaults.update(overrides)
    request = DacaRequest(**defaults)
    db.add(request)
    await db.flush()
    return request


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------

async def create_agreement(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    **overrides,
) -> Agreement:
    if daca_request is None:
        daca_request = await create_daca_request(db)
    defaults = {
        "daca_request_id": daca_request.id,
        "template_version": "10.24.25",
        "agreement_type": "ORIGINAL",
        "signing_status": "DRAFT",
    }
    defaults.update(overrides)
    agreement = Agreement(**defaults)
    db.add(agreement)
    await db.flush()
    return agreement


# ---------------------------------------------------------------------------
# CompliancePackage
# ---------------------------------------------------------------------------

async def create_compliance_package(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    **overrides,
) -> CompliancePackage:
    if daca_request is None:
        daca_request = await create_daca_request(db)
    defaults = {
        "daca_request_id": daca_request.id,
    }
    defaults.update(overrides)
    package = CompliancePackage(**defaults)
    db.add(package)
    await db.flush()
    return package


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

async def create_account(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    **overrides,
) -> Account:
    if daca_request is None:
        daca_request = await create_daca_request(db)
    defaults = {
        "daca_request_id": daca_request.id,
        "account_type": "CHECKING",
        "routing_number": fake.numerify(text="#########"),
        "account_status": "PENDING_SETUP",
        "control_status": "BORROWER_CONTROL",
        "is_new_account": True,
        "sweep_cadence": "NEVER",
    }
    defaults.update(overrides)
    account = Account(**defaults)
    db.add(account)
    await db.flush()
    return account


# ---------------------------------------------------------------------------
# TriggerEvent
# ---------------------------------------------------------------------------

async def create_trigger_event(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    account: Account | None = None,
    **overrides,
) -> TriggerEvent:
    if daca_request is None:
        daca_request = await create_daca_request(db)
    defaults = {
        "daca_request_id": daca_request.id,
        "account_id": account.id if account else None,
        "event_type": "SPRINGING_TRIGGER",
        "requested_by_email": fake.email(),
        "requested_by_name": fake.name(),
        "requested_at": datetime.now(timezone.utc),
        "verification_status": "PENDING",
    }
    defaults.update(overrides)
    event = TriggerEvent(**defaults)
    db.add(event)
    await db.flush()
    return event


# ---------------------------------------------------------------------------
# EmailThread
# ---------------------------------------------------------------------------

async def create_email_thread(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    **overrides,
) -> EmailThread:
    defaults = {
        "daca_request_id": daca_request.id if daca_request else None,
        "gmail_thread_id": fake.uuid4(),
        "subject": f"RE: DACA Setup - {fake.company()}",
        "participants": [fake.email(), "daca@rho.co"],
        "last_message_at": datetime.now(timezone.utc),
        "last_sender": fake.email(),
        "last_snippet": fake.sentence(nb_words=10),
        "awaiting_response": False,
        "thread_status": "ACTIVE",
    }
    defaults.update(overrides)
    thread = EmailThread(**defaults)
    db.add(thread)
    await db.flush()
    return thread


# ---------------------------------------------------------------------------
# EmailDraft
# ---------------------------------------------------------------------------

async def create_email_draft(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    email_thread: EmailThread | None = None,
    **overrides,
) -> EmailDraft:
    defaults = {
        "daca_request_id": daca_request.id if daca_request else None,
        "email_thread_id": email_thread.id if email_thread else None,
        "draft_type": "INTRO_KICKOFF",
        "to_addresses": [fake.email()],
        "cc_addresses": ["daca@rho.co"],
        "subject": f"DACA Setup - {fake.company()}",
        "body_html": f"<p>{fake.paragraph()}</p>",
        "body_text": fake.paragraph(),
        "status": "PENDING_REVIEW",
    }
    defaults.update(overrides)
    draft = EmailDraft(**defaults)
    db.add(draft)
    await db.flush()
    return draft


# ---------------------------------------------------------------------------
# HumanReviewItem
# ---------------------------------------------------------------------------

async def create_human_review_item(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    **overrides,
) -> HumanReviewItem:
    if daca_request is None:
        daca_request = await create_daca_request(db)
    defaults = {
        "daca_request_id": daca_request.id,
        "stage": DacaRequestStatus.FRAUD_INITIAL_REVIEW,
        "review_type": "GATE_APPROVAL",
        "status": "PENDING",
        "agent_recommendation": "Approve based on clean KYB checks.",
        "agent_confidence": 0.92,
        "agent_name": "IntakeAgent",
    }
    defaults.update(overrides)
    item = HumanReviewItem(**defaults)
    db.add(item)
    await db.flush()
    return item


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------

async def create_audit_log(
    db: AsyncSession,
    *,
    daca_request: DacaRequest | None = None,
    **overrides,
) -> AuditLog:
    entity_id = overrides.pop("entity_id", None) or (
        daca_request.id if daca_request else uuid.uuid4()
    )
    defaults = {
        "daca_request_id": daca_request.id if daca_request else None,
        "entity_type": "DacaRequest",
        "entity_id": entity_id,
        "action": "created",
        "actor_type": ActorType.HUMAN,
        "actor_id": "local_operator",
    }
    defaults.update(overrides)
    log = AuditLog(**defaults)
    db.add(log)
    await db.flush()
    return log


# ---------------------------------------------------------------------------
# OversightConfig
# ---------------------------------------------------------------------------

async def create_oversight_config(
    db: AsyncSession,
    **overrides,
) -> OversightConfig:
    defaults = {
        "scope": "SYSTEM",
        "stage": None,
        "mode": OversightMode.HUMAN_OVERSIGHT,
        "confidence_threshold": 0.85,
        "enabled": True,
        "updated_by": "test",
    }
    defaults.update(overrides)
    config = OversightConfig(**defaults)
    db.add(config)
    await db.flush()
    return config


# ---------------------------------------------------------------------------
# OpsManualVersion
# ---------------------------------------------------------------------------

async def create_ops_manual_version(
    db: AsyncSession,
    *,
    is_current: bool = True,
    **overrides,
) -> OpsManualVersion:
    defaults = {
        "drive_file_id": fake.uuid4(),
        "drive_file_name": "DACA Operations Manual v2.1.pdf",
        "version_label": "DACA Operations Manual v2.1",
        "fetched_at": datetime.now(timezone.utc),
        "is_current": is_current,
    }
    defaults.update(overrides)
    version = OpsManualVersion(**defaults)
    db.add(version)
    await db.flush()
    return version
