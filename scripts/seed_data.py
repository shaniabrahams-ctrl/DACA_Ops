"""
Seed script — populates the database with realistic DACA operations data
so every page in the UI has something to show.

Usage: python -m scripts.seed_data
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from app.db.session import engine, AsyncSessionLocal, _is_sqlite
from app.db.base import Base
import app.models  # noqa: F401

now = datetime.now(timezone.utc)


def hours_ago(h: int) -> datetime:
    return now - timedelta(hours=h)


def days_ago(d: int) -> datetime:
    return now - timedelta(days=d)


# Pre-generate stable UUIDs so we can cross-reference
BORROWER_IDS = [uuid.uuid4() for _ in range(8)]
LENDER_IDS = [uuid.uuid4() for _ in range(5)]
REQUEST_IDS = [uuid.uuid4() for _ in range(8)]
ACCOUNT_IDS = [uuid.uuid4() for _ in range(6)]

BORROWERS = [
    dict(id=BORROWER_IDS[0], legal_name="Greenfield Capital LLC", rho_id="1046", entity_type="LLC",
         state_of_formation="Delaware", primary_contact_name="Maria Chen",
         primary_contact_email="maria.chen@greenfieldcap.com", kyb_status="VERIFIED",
         has_rho_account=True, created_at=days_ago(45), updated_at=days_ago(45)),
    dict(id=BORROWER_IDS[1], legal_name="Apex Manufacturing Corp", rho_id="1102", entity_type="CORP",
         state_of_formation="New York", primary_contact_name="David Park",
         primary_contact_email="dpark@apexmfg.com", kyb_status="VERIFIED",
         has_rho_account=True, created_at=days_ago(30), updated_at=days_ago(30)),
    dict(id=BORROWER_IDS[2], legal_name="Northstar Logistics Inc", rho_id="1158", entity_type="CORP",
         state_of_formation="California", primary_contact_name="Sarah Williams",
         primary_contact_email="swilliams@northstarlog.com", kyb_status="VERIFIED",
         has_rho_account=True, created_at=days_ago(25), updated_at=days_ago(25)),
    dict(id=BORROWER_IDS[3], legal_name="BrightPath Healthcare LP", rho_id="1201", entity_type="LP",
         state_of_formation="Texas", primary_contact_name="James Morrison",
         primary_contact_email="jmorrison@brightpath.health", kyb_status="VERIFIED",
         has_rho_account=True, created_at=days_ago(20), updated_at=days_ago(20)),
    dict(id=BORROWER_IDS[4], legal_name="Cascade Technology Solutions LLC", rho_id="1245", entity_type="LLC",
         state_of_formation="Washington", primary_contact_name="Linda Torres",
         primary_contact_email="ltorres@cascadetech.io", kyb_status="PENDING",
         has_rho_account=False, created_at=days_ago(5), updated_at=days_ago(5)),
    dict(id=BORROWER_IDS[5], legal_name="Summit Real Estate Holdings LLC", rho_id="1289", entity_type="LLC",
         state_of_formation="Florida", primary_contact_name="Robert Kim",
         primary_contact_email="rkim@summitrealestate.com", kyb_status="VERIFIED",
         has_rho_account=True, created_at=days_ago(60), updated_at=days_ago(60)),
    dict(id=BORROWER_IDS[6], legal_name="BlueWave Energy Corp", rho_id="1312", entity_type="CORP",
         state_of_formation="Colorado", primary_contact_name="Amanda Foster",
         primary_contact_email="afoster@bluewave-energy.com", kyb_status="VERIFIED",
         has_rho_account=True, created_at=days_ago(15), updated_at=days_ago(15)),
    dict(id=BORROWER_IDS[7], legal_name="Pinnacle Construction Group Inc", rho_id="1350", entity_type="CORP",
         state_of_formation="New Jersey", primary_contact_name="Michael Zhang",
         primary_contact_email="mzhang@pinnacleconst.com", kyb_status="PENDING",
         has_rho_account=False, created_at=days_ago(2), updated_at=days_ago(2)),
]

LENDERS = [
    dict(id=LENDER_IDS[0], institution_name="Silicon Valley Bank",
         business_address="3003 Tasman Dr, Santa Clara, CA 95054",
         primary_contact_email="daca-ops@svb.com", daca_type="SPRINGING",
         representatives=[{"name": "Jennifer Walsh", "email": "jwalsh@svb.com", "phone": "408-555-0101"}],
         created_at=days_ago(60), updated_at=days_ago(60)),
    dict(id=LENDER_IDS[1], institution_name="JPMorgan Chase Bank N.A.",
         business_address="383 Madison Ave, New York, NY 10179",
         primary_contact_email="daca-team@jpmorgan.com", daca_type="SPRINGING",
         representatives=[{"name": "Thomas Reid", "email": "treid@jpmorgan.com", "phone": "212-555-0202"}],
         created_at=days_ago(45), updated_at=days_ago(45)),
    dict(id=LENDER_IDS[2], institution_name="First Republic Bank",
         business_address="111 Pine St, San Francisco, CA 94111",
         primary_contact_email="lending@firstrepublic.com", daca_type="SPRINGING",
         representatives=[{"name": "Karen Liu", "email": "kliu@firstrepublic.com", "phone": "415-555-0303"}],
         created_at=days_ago(30), updated_at=days_ago(30)),
    dict(id=LENDER_IDS[3], institution_name="Bank of America N.A.",
         business_address="100 N Tryon St, Charlotte, NC 28255",
         primary_contact_email="commercial-lending@bofa.com", daca_type="SPRINGING",
         representatives=[{"name": "Steven Clark", "email": "sclark@bofa.com", "phone": "704-555-0404"}],
         created_at=days_ago(20), updated_at=days_ago(20)),
    dict(id=LENDER_IDS[4], institution_name="Comerica Bank",
         business_address="1717 Main St, Dallas, TX 75201",
         primary_contact_email="daca@comerica.com", daca_type="SPRINGING",
         representatives=[{"name": "Patricia Santos", "email": "psantos@comerica.com", "phone": "214-555-0505"}],
         created_at=days_ago(10), updated_at=days_ago(10)),
]

# 8 requests at different lifecycle stages
REQUESTS = [
    # 1. Done — fully completed 30 days ago
    dict(id=REQUEST_IDS[0], external_ref="DACA-2026-0038", borrower_id=BORROWER_IDS[0],
         lender_id=LENDER_IDS[0], status="Done", previous_status="Pending Final Setup",
         priority="NORMAL", source_channel="EMAIL", jira_ticket_key="CS-438",
         assigned_to="shani.abrahams@rho.co", created_at=days_ago(45), updated_at=days_ago(30)),
    # 2. Pending Final Setup — agreement signed, waiting for account activation
    dict(id=REQUEST_IDS[1], external_ref="DACA-2026-0041", borrower_id=BORROWER_IDS[1],
         lender_id=LENDER_IDS[1], status="Pending Final Setup", previous_status="Docusign Sent",
         priority="HIGH", source_channel="EMAIL", jira_ticket_key="CS-441",
         assigned_to="shani.abrahams@rho.co", created_at=days_ago(30), updated_at=days_ago(3)),
    # 3. DocuSign Sent — waiting for signatures
    dict(id=REQUEST_IDS[2], external_ref="DACA-2026-0044", borrower_id=BORROWER_IDS[2],
         lender_id=LENDER_IDS[2], status="Docusign Sent", previous_status="Pre-Webster Review",
         priority="NORMAL", source_channel="TYPEFORM", jira_ticket_key="CS-444",
         typeform_token="tf_abc123", assigned_to="shani.abrahams@rho.co",
         created_at=days_ago(25), updated_at=days_ago(7)),
    # 4. Pre-Webster Review — compliance package assembled, awaiting Shani's approval
    dict(id=REQUEST_IDS[3], external_ref="DACA-2026-0047", borrower_id=BORROWER_IDS[3],
         lender_id=LENDER_IDS[3], status="Pre-Webster Review",
         previous_status="Pending Compliance Package Assembly",
         priority="NORMAL", source_channel="EMAIL", jira_ticket_key="CS-447",
         assigned_to="shani.abrahams@rho.co", created_at=days_ago(20), updated_at=days_ago(2)),
    # 5. Pending Compliance — gathering documents
    dict(id=REQUEST_IDS[4], external_ref="DACA-2026-0050", borrower_id=BORROWER_IDS[5],
         lender_id=LENDER_IDS[0], status="Pending Compliance Package Assembly",
         previous_status="Templates/Agreements Sent",
         priority="NORMAL", source_channel="TYPEFORM", jira_ticket_key="CS-450",
         typeform_token="tf_def456", assigned_to="shani.abrahams@rho.co",
         created_at=days_ago(15), updated_at=days_ago(1)),
    # 6. Legal Redline Review — lender wants non-standard terms
    dict(id=REQUEST_IDS[5], external_ref="DACA-2026-0052", borrower_id=BORROWER_IDS[6],
         lender_id=LENDER_IDS[4], status="Legal Redline Review",
         previous_status="Typeform Sent", has_redlines=True,
         priority="HIGH", source_channel="EMAIL", jira_ticket_key="CS-452",
         assigned_to="shani.abrahams@rho.co", created_at=days_ago(15), updated_at=hours_ago(18)),
    # 7. Fraud Initial Review — brand new, just came in
    dict(id=REQUEST_IDS[6], external_ref="DACA-2026-0055", borrower_id=BORROWER_IDS[4],
         lender_id=LENDER_IDS[2], status="Fraud Initial Review",
         priority="NORMAL", source_channel="TYPEFORM", jira_ticket_key="CS-455",
         typeform_token="tf_ghi789", created_at=days_ago(2), updated_at=days_ago(2)),
    # 8. Triggered — springing trigger event in progress
    dict(id=REQUEST_IDS[7], external_ref="DACA-2026-0035", borrower_id=BORROWER_IDS[5],
         lender_id=LENDER_IDS[0], status="Triggered", previous_status="Done",
         priority="URGENT", source_channel="EMAIL", jira_ticket_key="CS-435",
         assigned_to="shani.abrahams@rho.co", created_at=days_ago(90), updated_at=hours_ago(4)),
]

AGREEMENTS = [
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[0], template_version="10.24.25",
         signing_status="COMPLETED", borrower_signed_at=days_ago(35),
         lender_signed_at=days_ago(34), rho_signed_at=days_ago(33),
         webster_signed_at=days_ago(32), effective_date=days_ago(32).date(),
         created_at=days_ago(40), updated_at=days_ago(30)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[1], template_version="10.24.25",
         signing_status="COMPLETED", borrower_signed_at=days_ago(8),
         lender_signed_at=days_ago(7), rho_signed_at=days_ago(5),
         webster_signed_at=days_ago(4), effective_date=days_ago(4).date(),
         created_at=days_ago(25), updated_at=days_ago(3)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[2], template_version="10.24.25",
         signing_status="SENT", docusign_envelope_id="env-abc-123-def",
         borrower_signed_at=days_ago(5),
         created_at=days_ago(20), updated_at=days_ago(5)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3], template_version="10.24.25",
         signing_status="DRAFT",
         created_at=days_ago(15), updated_at=days_ago(2)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[4], template_version="10.24.25",
         signing_status="DRAFT",
         created_at=days_ago(12), updated_at=days_ago(1)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[5], template_version="10.24.25",
         signing_status="DRAFT", has_redlines=True,
         redlines_notes="Lender requesting modified notice period (5 business days instead of 3)",
         created_at=days_ago(12), updated_at=hours_ago(18)),
]

COMPLIANCE_PACKAGES = [
    # Completed package for Done request
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[0],
         typeform_pdf_attached=True, loan_agreement_uploaded=True,
         compliance_approved=True, compliance_approved_by="vladan@rho.co",
         compliance_approved_at=days_ago(38),
         middesk_report_uploaded=True, middesk_address_matches_rap=True,
         ein_tin_match_verified=True, alloy_report_verified=True,
         signatory_ubo_reports_verified=True, signatory_equals_ubo=True,
         articles_of_incorporation_uploaded=True,
         daca_dri_review_approved=True, daca_dri_review_approved_by="shani.abrahams@rho.co",
         daca_dri_review_approved_at=days_ago(36),
         webster_approval_status="APPROVED", webster_submission_date=days_ago(35),
         created_at=days_ago(42), updated_at=days_ago(30)),
    # Completed for Pending Final Setup
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[1],
         typeform_pdf_attached=True, loan_agreement_uploaded=True,
         compliance_approved=True, compliance_approved_by="vladan@rho.co",
         compliance_approved_at=days_ago(18),
         middesk_report_uploaded=True, middesk_address_matches_rap=True,
         ein_tin_match_verified=True, alloy_report_verified=True,
         signatory_ubo_reports_verified=True, signatory_equals_ubo=False,
         articles_of_incorporation_uploaded=True,
         daca_dri_review_approved=True, daca_dri_review_approved_by="shani.abrahams@rho.co",
         daca_dri_review_approved_at=days_ago(15),
         webster_approval_status="APPROVED", webster_submission_date=days_ago(14),
         created_at=days_ago(28), updated_at=days_ago(3)),
    # Completed for DocuSign Sent
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[2],
         typeform_pdf_attached=True, loan_agreement_uploaded=True,
         compliance_approved=True, compliance_approved_by="vladan@rho.co",
         compliance_approved_at=days_ago(15),
         middesk_report_uploaded=True, middesk_address_matches_rap=True,
         ein_tin_match_verified=True, alloy_report_verified=True,
         signatory_ubo_reports_verified=True, signatory_equals_ubo=True,
         articles_of_incorporation_uploaded=True,
         daca_dri_review_approved=True, daca_dri_review_approved_by="shani.abrahams@rho.co",
         daca_dri_review_approved_at=days_ago(12),
         webster_approval_status="APPROVED", webster_submission_date=days_ago(11),
         created_at=days_ago(22), updated_at=days_ago(7)),
    # Ready for Pre-Webster review — assembled but not yet reviewed
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3],
         typeform_pdf_attached=True, loan_agreement_uploaded=True,
         compliance_approved=True, compliance_approved_by="vladan@rho.co",
         compliance_approved_at=days_ago(5),
         middesk_report_uploaded=True, middesk_address_matches_rap=True,
         ein_tin_match_verified=True, alloy_report_verified=True,
         signatory_ubo_reports_verified=True, signatory_equals_ubo=True,
         articles_of_incorporation_uploaded=True,
         daca_dri_review_approved=False,
         webster_approval_status="NOT_SUBMITTED",
         created_at=days_ago(18), updated_at=days_ago(2)),
    # Partially assembled — missing some docs
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[4],
         typeform_pdf_attached=True, loan_agreement_uploaded=False,
         compliance_approved=True, compliance_approved_by="vladan@rho.co",
         compliance_approved_at=days_ago(8),
         middesk_report_uploaded=True, middesk_address_matches_rap=True,
         ein_tin_match_verified=True, alloy_report_verified=False,
         signatory_ubo_reports_verified=False,
         articles_of_incorporation_uploaded=True,
         webster_approval_status="NOT_SUBMITTED",
         created_at=days_ago(14), updated_at=days_ago(1)),
]

ACCOUNTS = [
    # Done request — active account
    dict(id=ACCOUNT_IDS[0], daca_request_id=REQUEST_IDS[0], account_type="CHECKING",
         routing_number="211170101", account_status="ACTIVE",
         control_status="BORROWER_CONTROL", is_new_account=True,
         activated_at=days_ago(30), sweep_cadence="NEVER",
         created_at=days_ago(38), updated_at=days_ago(30)),
    # Pending Final Setup — account pending activation
    dict(id=ACCOUNT_IDS[1], daca_request_id=REQUEST_IDS[1], account_type="CHECKING",
         routing_number="211170101", account_status="PENDING_SETUP",
         control_status="BORROWER_CONTROL", is_new_account=True,
         eng_ticket_key="ENG-36102",
         created_at=days_ago(10), updated_at=days_ago(3)),
    # Triggered request — account now under lender control
    dict(id=ACCOUNT_IDS[2], daca_request_id=REQUEST_IDS[7], account_type="CHECKING",
         routing_number="211170101", account_status="ACTIVE",
         control_status="LENDER_CONTROL", is_new_account=True,
         activated_at=days_ago(80), sweep_cadence="DAILY",
         lender_ach_routing="021000021",
         created_at=days_ago(85), updated_at=hours_ago(4)),
]

TRIGGER_EVENTS = [
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[7], account_id=ACCOUNT_IDS[2],
         event_type="SPRINGING_TRIGGER",
         requested_by_email="jwalsh@svb.com", requested_by_name="Jennifer Walsh",
         requested_at=hours_ago(4), lender_notified_webster=True,
         email_verified=True, email_verification_method="SALESFORCE_MATCH",
         lender_external_bank_details_provided=True,
         jira_ticket_key="CS-460", verification_status="VERIFIED",
         executed_at=hours_ago(3), executed_by="shani.abrahams@rho.co",
         blocked_in_rap_at=hours_ago(3), reactivated_after_block_at=hours_ago(3),
         control_change_from="BORROWER_CONTROL", control_change_to="LENDER_CONTROL",
         lender_notified_at=hours_ago(2),
         created_at=hours_ago(4), updated_at=hours_ago(2)),
]

HUMAN_REVIEW_ITEMS = [
    # Pending: Pre-Webster Review gate
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3],
         stage="Pre-Webster Review", review_type="GATE_APPROVAL",
         agent_recommendation="All 11 compliance checklist items satisfied. Recommend approval for Webster submission.",
         agent_confidence=0.92, agent_name="ComplianceAssemblyAgent",
         status="PENDING", assigned_to="shani.abrahams@rho.co",
         sla_deadline=hours_ago(-8),
         payload={"checklist_complete": True, "items_verified": 11, "items_total": 11},
         created_at=days_ago(2), updated_at=days_ago(2)),
    # Pending: Fraud Initial Review
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[6],
         stage="Fraud Initial Review", review_type="GATE_APPROVAL",
         agent_recommendation="New application from Cascade Technology Solutions. KYB status pending. Standard Typeform submission with complete fields.",
         agent_confidence=0.78, agent_name="IntakeAgent",
         status="PENDING", assigned_to="shani.abrahams@rho.co",
         sla_deadline=hours_ago(-4),
         payload={"borrower": "Cascade Technology Solutions LLC", "source": "TYPEFORM"},
         created_at=days_ago(2), updated_at=days_ago(2)),
    # Pending: Legal Redline Review
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[5],
         stage="Legal Redline Review", review_type="GATE_APPROVAL",
         agent_recommendation="Lender (Comerica) requests 5 business day notice period instead of standard 3. This deviates from Webster-approved template.",
         agent_confidence=0.65, agent_name="AgreementGenerationAgent",
         status="PENDING", assigned_to="shani.abrahams@rho.co",
         payload={"redline_type": "notice_period", "requested": "5 business days", "standard": "3 business days"},
         created_at=hours_ago(18), updated_at=hours_ago(18)),
    # Completed: Previous fraud review (approved)
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3],
         stage="Fraud Initial Review", review_type="GATE_APPROVAL",
         agent_recommendation="Standard application from BrightPath Healthcare LP. Entity verified through Middesk.",
         agent_confidence=0.95, agent_name="IntakeAgent",
         status="APPROVED", assigned_to="shani.abrahams@rho.co",
         reviewed_by="shani.abrahams@rho.co", reviewed_at=days_ago(19),
         review_notes="Approved — clean Middesk report, known lender.",
         created_at=days_ago(20), updated_at=days_ago(19)),
]

EMAIL_THREADS = [
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3],
         gmail_thread_id="thread_001", subject="DACA Setup — BrightPath Healthcare LP / Bank of America",
         participants=["daca@rho.co", "jmorrison@brightpath.health", "sclark@bofa.com"],
         last_message_at=days_ago(3), last_sender="jmorrison@brightpath.health",
         last_snippet="Hi Shani, attached are the remaining compliance documents you requested...",
         awaiting_response=True, thread_status="ACTIVE",
         created_at=days_ago(18), updated_at=days_ago(3)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[2],
         gmail_thread_id="thread_002", subject="DocuSign Sent — Northstar Logistics / First Republic",
         participants=["daca@rho.co", "swilliams@northstarlog.com", "kliu@firstrepublic.com"],
         last_message_at=days_ago(7), last_sender="daca@rho.co",
         last_snippet="The DocuSign envelope has been sent for execution. Please sign at your earliest convenience.",
         awaiting_response=False, thread_status="ACTIVE",
         created_at=days_ago(10), updated_at=days_ago(7)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[5],
         gmail_thread_id="thread_003", subject="RE: DACA Template — BlueWave Energy / Comerica — Redline Request",
         participants=["daca@rho.co", "afoster@bluewave-energy.com", "psantos@comerica.com"],
         last_message_at=hours_ago(18), last_sender="psantos@comerica.com",
         last_snippet="We would need the notice period extended to 5 business days per our internal policy...",
         awaiting_response=True, thread_status="ACTIVE",
         created_at=days_ago(12), updated_at=hours_ago(18)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[7],
         gmail_thread_id="thread_004", subject="URGENT: Springing Trigger — Summit Real Estate / SVB",
         participants=["daca@rho.co", "jwalsh@svb.com", "webster_rho_daca@websterbank.com",
                        "mike.szarowicz@rho.co"],
         last_message_at=hours_ago(2), last_sender="daca@rho.co",
         last_snippet="Trigger event has been executed. Account control transferred to SVB per the springing DACA.",
         awaiting_response=False, thread_status="ACTIVE",
         created_at=hours_ago(4), updated_at=hours_ago(2)),
]

EMAIL_DRAFTS = [
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3],
         draft_type="FOLLOW_UP", trigger_event="3_days_no_docs",
         to_addresses=["jmorrison@brightpath.health"],
         cc_addresses=["daca@rho.co", "sclark@bofa.com"],
         subject="Follow-up: Outstanding Compliance Documents — DACA-2026-0047",
         body_html="<p>Hi James,</p><p>This is a follow-up regarding the remaining compliance documents needed for your DACA setup. We're still awaiting:</p><ul><li>Loan agreement (optional but recommended)</li><li>Updated Alloy entity report</li></ul><p>Could you please provide these at your earliest convenience so we can proceed with the Webster Bank submission?</p><p>Best regards,<br>DACA Operations Team<br>Rho</p>",
         body_text="Hi James,\n\nThis is a follow-up regarding the remaining compliance documents needed for your DACA setup. We're still awaiting:\n- Loan agreement (optional but recommended)\n- Updated Alloy entity report\n\nCould you please provide these at your earliest convenience so we can proceed with the Webster Bank submission?\n\nBest regards,\nDACA Operations Team\nRho",
         ai_model_used="claude-sonnet-4-6", status="PENDING_REVIEW",
         created_at=days_ago(1), updated_at=days_ago(1)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[6],
         draft_type="INTRO_KICKOFF", trigger_event="status_changed_to_TYPEFORM_SENT",
         to_addresses=["ltorres@cascadetech.io"],
         cc_addresses=["daca@rho.co", "kliu@firstrepublic.com"],
         subject="DACA Process Kick-off — Cascade Technology Solutions / First Republic Bank",
         body_html="<p>Hi Linda,</p><p>Thank you for submitting your DACA request. We've received your application and are beginning the setup process.</p><p>Here's what to expect next:</p><ol><li>We'll review your application and verify your entity information</li><li>You'll receive the Springing DACA template for review</li><li>Once all parties have reviewed, we'll send via DocuSign for signatures</li></ol><p>If you have any questions, please reply to this email thread.</p><p>Best regards,<br>DACA Operations Team<br>Rho</p>",
         body_text="Hi Linda,\n\nThank you for submitting your DACA request. We've received your application and are beginning the setup process.\n\nHere's what to expect next:\n1. We'll review your application and verify your entity information\n2. You'll receive the Springing DACA template for review\n3. Once all parties have reviewed, we'll send via DocuSign for signatures\n\nIf you have any questions, please reply to this email thread.\n\nBest regards,\nDACA Operations Team\nRho",
         ai_model_used="claude-sonnet-4-6", status="PENDING_REVIEW",
         created_at=days_ago(2), updated_at=days_ago(2)),
]

AUDIT_LOGS = [
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[7],
         entity_type="DacaRequest", entity_id=REQUEST_IDS[7],
         action="status_change", actor_type="HUMAN", actor_id="shani.abrahams@rho.co",
         before_state={"status": "Done"}, after_state={"status": "Triggered"},
         rationale="Springing trigger event received from SVB (Jennifer Walsh)",
         ops_manual_version="DACA Operations Manual v2.1",
         created_at=hours_ago(4)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[7],
         entity_type="TriggerEvent", entity_id=REQUEST_IDS[7],
         action="trigger_event_executed", actor_type="HUMAN", actor_id="shani.abrahams@rho.co",
         after_state={"verification_status": "VERIFIED", "control_change_to": "LENDER_CONTROL"},
         rationale="Email verified via Salesforce match. Account blocked and reactivated under lender control.",
         ops_manual_version="DACA Operations Manual v2.1",
         created_at=hours_ago(3)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[3],
         entity_type="DacaRequest", entity_id=REQUEST_IDS[3],
         action="status_change", actor_type="AGENT", actor_id="ComplianceAssemblyAgent",
         before_state={"status": "Pending Compliance Package Assembly"},
         after_state={"status": "Pre-Webster Review"},
         rationale="All required compliance documents gathered and verified. Package ready for DRI review.",
         ops_manual_version="DACA Operations Manual v2.1",
         created_at=days_ago(2)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[6],
         entity_type="DacaRequest", entity_id=REQUEST_IDS[6],
         action="created", actor_type="SYSTEM", actor_id="system",
         after_state={"status": "Fraud Initial Review", "source": "TYPEFORM"},
         rationale="New DACA request created from Typeform submission",
         ops_manual_version="DACA Operations Manual v2.1",
         created_at=days_ago(2)),
    dict(id=uuid.uuid4(), daca_request_id=REQUEST_IDS[2],
         entity_type="DacaRequest", entity_id=REQUEST_IDS[2],
         action="status_change", actor_type="HUMAN", actor_id="shani.abrahams@rho.co",
         before_state={"status": "Pre-Webster Review"}, after_state={"status": "Docusign Sent"},
         rationale="Webster approved compliance package. DocuSign envelope sent.",
         ops_manual_version="DACA Operations Manual v2.1",
         created_at=days_ago(7)),
]

OVERSIGHT_CONFIGS = [
    dict(id=uuid.uuid4(), scope="SYSTEM", stage=None,
         mode="HUMAN_OVERSIGHT", confidence_threshold=0.85, enabled=True,
         updated_by="shani.abrahams@rho.co",
         created_at=days_ago(60), updated_at=days_ago(60)),
]

OPS_MANUAL_VERSIONS = [
    dict(id=uuid.uuid4(), drive_file_id="1abc_ops_manual_v21",
         drive_file_name="DACA Operations Manual v2.1.docx",
         version_label="DACA Operations Manual v2.1",
         fetched_at=days_ago(7), is_current=True,
         created_at=days_ago(7), updated_at=days_ago(7)),
]


async def seed():
    from app.models.borrower import Borrower
    from app.models.lender import Lender
    from app.models.daca_request import DacaRequest
    from app.models.agreement import Agreement
    from app.models.compliance_package import CompliancePackage
    from app.models.account import Account
    from app.models.trigger_event import TriggerEvent
    from app.models.human_review import HumanReviewItem
    from app.models.email_thread import EmailThread
    from app.models.email_draft import EmailDraft
    from app.models.audit_log import AuditLog
    from app.models.oversight_config import OversightConfig
    from app.models.ops_manual_version import OpsManualVersion

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if data already exists
        from sqlalchemy import select, func
        result = await session.execute(select(func.count()).select_from(DacaRequest))
        count = result.scalar()
        if count and count > 0:
            print(f"Database already has {count} DACA requests — skipping seed.")
            return

        for data in BORROWERS:
            session.add(Borrower(**data))
        for data in LENDERS:
            session.add(Lender(**data))
        await session.flush()

        for data in REQUESTS:
            session.add(DacaRequest(**data))
        await session.flush()

        for data in AGREEMENTS:
            session.add(Agreement(**data))
        for data in COMPLIANCE_PACKAGES:
            session.add(CompliancePackage(**data))
        for data in ACCOUNTS:
            session.add(Account(**data))
        await session.flush()

        for data in TRIGGER_EVENTS:
            session.add(TriggerEvent(**data))
        for data in HUMAN_REVIEW_ITEMS:
            session.add(HumanReviewItem(**data))
        for data in EMAIL_THREADS:
            session.add(EmailThread(**data))
        for data in EMAIL_DRAFTS:
            session.add(EmailDraft(**data))
        for data in AUDIT_LOGS:
            session.add(AuditLog(**data))
        for data in OVERSIGHT_CONFIGS:
            session.add(OversightConfig(**data))
        for data in OPS_MANUAL_VERSIONS:
            session.add(OpsManualVersion(**data))

        await session.commit()
        print("Seed data created successfully!")
        print(f"  - {len(BORROWERS)} borrowers")
        print(f"  - {len(LENDERS)} lenders")
        print(f"  - {len(REQUESTS)} DACA requests")
        print(f"  - {len(AGREEMENTS)} agreements")
        print(f"  - {len(COMPLIANCE_PACKAGES)} compliance packages")
        print(f"  - {len(ACCOUNTS)} accounts")
        print(f"  - {len(TRIGGER_EVENTS)} trigger events")
        print(f"  - {len(HUMAN_REVIEW_ITEMS)} human review items")
        print(f"  - {len(EMAIL_THREADS)} email threads")
        print(f"  - {len(EMAIL_DRAFTS)} email drafts")
        print(f"  - {len(AUDIT_LOGS)} audit logs")
        print(f"  - {len(OVERSIGHT_CONFIGS)} oversight configs")
        print(f"  - {len(OPS_MANUAL_VERSIONS)} ops manual versions")


if __name__ == "__main__":
    asyncio.run(seed())
