"""Initial schema — all DACA Operations Platform tables.

Revision ID: 001
Revises:
Create Date: 2026-04-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Borrowers
    op.create_table(
        'borrowers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('rho_id', sa.String(50), unique=True, nullable=True),
        sa.Column('legal_name', sa.String(500), nullable=False),
        sa.Column('dba_name', sa.String(500), nullable=True),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('state_of_formation', sa.String(100), nullable=True),
        sa.Column('ein_encrypted', sa.Text, nullable=True),
        sa.Column('address', postgresql.JSONB, nullable=True),
        sa.Column('primary_contact_name', sa.String(300), nullable=True),
        sa.Column('primary_contact_email', sa.String(300), nullable=True),
        sa.Column('primary_contact_phone', sa.String(50), nullable=True),
        sa.Column('salesforce_account_id', sa.String(50), nullable=True),
        sa.Column('has_rho_account', sa.Boolean, default=False),
        sa.Column('kyb_status', sa.String(50), default='PENDING'),
        sa.Column('middesk_report_url', sa.Text, nullable=True),
        sa.Column('alloy_report_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_borrowers_rho_id', 'borrowers', ['rho_id'])
    op.create_index('ix_borrowers_primary_contact_email', 'borrowers', ['primary_contact_email'])
    op.create_index('ix_borrowers_salesforce_account_id', 'borrowers', ['salesforce_account_id'])

    # Lenders
    op.create_table(
        'lenders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_name', sa.String(500), nullable=False),
        sa.Column('business_address', sa.Text, nullable=True),
        sa.Column('rep_count', sa.Integer, default=1),
        sa.Column('representatives', postgresql.JSONB, nullable=True),
        sa.Column('primary_contact_email', sa.String(300), nullable=True),
        sa.Column('primary_contact_phone', sa.String(50), nullable=True),
        sa.Column('daca_type', sa.String(50), default='SPRINGING'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_lenders_primary_contact_email', 'lenders', ['primary_contact_email'])

    # DACA Requests
    op.create_table(
        'daca_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('external_ref', sa.String(50), unique=True, nullable=False),
        sa.Column('borrower_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('borrowers.id'), nullable=True),
        sa.Column('lender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('lenders.id'), nullable=True),
        sa.Column('status', sa.String(100), nullable=False),
        sa.Column('previous_status', sa.String(100), nullable=True),
        sa.Column('priority', sa.String(20), default='NORMAL'),
        sa.Column('source_channel', sa.String(50), default='EMAIL'),
        sa.Column('source_reference', sa.String(500), nullable=True),
        sa.Column('typeform_token', sa.String(200), nullable=True),
        sa.Column('jira_ticket_key', sa.String(50), nullable=True),
        sa.Column('jira_status', sa.String(100), nullable=True),
        sa.Column('assigned_to', sa.String(200), nullable=True),
        sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('account_type_requested', sa.String(50), nullable=True),
        sa.Column('docusign_envelope_id', sa.String(200), nullable=True),
        sa.Column('has_redlines', sa.Boolean, default=False),
        sa.Column('redlines_approved_by', sa.String(200), nullable=True),
        sa.Column('redlines_notes', sa.Text, nullable=True),
        sa.Column('salesforce_checklist', postgresql.JSONB, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_daca_requests_external_ref', 'daca_requests', ['external_ref'])
    op.create_index('ix_daca_requests_status', 'daca_requests', ['status'])
    op.create_index('ix_daca_requests_borrower_id', 'daca_requests', ['borrower_id'])
    op.create_index('ix_daca_requests_lender_id', 'daca_requests', ['lender_id'])
    op.create_index('ix_daca_requests_typeform_token', 'daca_requests', ['typeform_token'])
    op.create_index('ix_daca_requests_jira_ticket_key', 'daca_requests', ['jira_ticket_key'])

    # Typeform Submissions
    op.create_table(
        'typeform_submissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=True),
        sa.Column('token', sa.String(200), unique=True, nullable=False),
        sa.Column('lender_legal_name', sa.String(500), nullable=True),
        sa.Column('lender_business_address', sa.Text, nullable=True),
        sa.Column('lender_rep_count', sa.Integer, nullable=True),
        sa.Column('lender_rep_1_name', sa.String(300), nullable=True),
        sa.Column('lender_rep_1_phone', sa.String(50), nullable=True),
        sa.Column('lender_rep_1_email', sa.String(300), nullable=True),
        sa.Column('lender_rep_2_name', sa.String(300), nullable=True),
        sa.Column('lender_rep_2_phone', sa.String(50), nullable=True),
        sa.Column('lender_rep_2_email', sa.String(300), nullable=True),
        sa.Column('lender_rep_3_name', sa.String(300), nullable=True),
        sa.Column('lender_rep_3_phone', sa.String(50), nullable=True),
        sa.Column('lender_rep_3_email', sa.String(300), nullable=True),
        sa.Column('borrower_has_rho_account', sa.Boolean, nullable=True),
        sa.Column('borrower_legal_name', sa.String(500), nullable=True),
        sa.Column('borrower_business_address', sa.Text, nullable=True),
        sa.Column('borrower_contact_name', sa.String(300), nullable=True),
        sa.Column('borrower_contact_email', sa.String(300), nullable=True),
        sa.Column('loan_agreement_url', sa.Text, nullable=True),
        sa.Column('referral_source', sa.String(200), nullable=True),
        sa.Column('government_receivables_involved', sa.Boolean, nullable=True),
        sa.Column('multiple_accounts_involved', sa.Boolean, nullable=True),
        sa.Column('preferred_transfer_method', sa.String(100), nullable=True),
        sa.Column('additional_info', sa.Text, nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_typeform_submissions_token', 'typeform_submissions', ['token'])
    op.create_index('ix_typeform_submissions_daca_request_id', 'typeform_submissions', ['daca_request_id'])

    # Compliance Packages
    op.create_table(
        'compliance_packages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False, unique=True),
        sa.Column('typeform_pdf_attached', sa.Boolean, default=False),
        sa.Column('loan_agreement_uploaded', sa.Boolean, default=False),
        sa.Column('compliance_approved', sa.Boolean, default=False),
        sa.Column('middesk_report_uploaded', sa.Boolean, default=False),
        sa.Column('middesk_address_matches_rap', sa.Boolean, default=False),
        sa.Column('ein_tin_match_verified', sa.Boolean, default=False),
        sa.Column('alloy_report_verified', sa.Boolean, default=False),
        sa.Column('signatory_ubo_reports_verified', sa.Boolean, default=False),
        sa.Column('articles_of_incorporation_uploaded', sa.Boolean, default=False),
        sa.Column('name_change_docs_uploaded', sa.Boolean, default=False),
        sa.Column('division_of_corps_filing_uploaded', sa.Boolean, default=False),
        sa.Column('pre_webster_reviewed_by', sa.String(200), nullable=True),
        sa.Column('pre_webster_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pre_webster_notes', sa.Text, nullable=True),
        sa.Column('webster_package_drive_id', sa.String(200), nullable=True),
        sa.Column('webster_package_drive_url', sa.Text, nullable=True),
        sa.Column('webster_submission_date', sa.Date, nullable=True),
        sa.Column('webster_approval_status', sa.String(50), nullable=True),
        sa.Column('webster_approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('webster_revisions_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_compliance_packages_daca_request_id', 'compliance_packages', ['daca_request_id'])

    # Agreements
    op.create_table(
        'agreements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False, unique=True),
        sa.Column('template_version', sa.String(50), default='10.24.25'),
        sa.Column('agreement_type', sa.String(50), default='ORIGINAL'),
        sa.Column('generated_document_drive_url', sa.Text, nullable=True),
        sa.Column('generated_document_drive_id', sa.String(200), nullable=True),
        sa.Column('docusign_envelope_id', sa.String(200), nullable=True),
        sa.Column('signing_status', sa.String(50), default='DRAFT'),
        sa.Column('borrower_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lender_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rho_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('webster_signed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_date', sa.Date, nullable=True),
        sa.Column('has_redlines', sa.Boolean, default=False),
        sa.Column('redlines_approved_by_legal', sa.Boolean, default=False),
        sa.Column('redlines_approved_by_webster', sa.Boolean, default=False),
        sa.Column('redlines_notes', sa.Text, nullable=True),
        sa.Column('executed_document_drive_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agreements_daca_request_id', 'agreements', ['daca_request_id'])
    op.create_index('ix_agreements_docusign_envelope_id', 'agreements', ['docusign_envelope_id'])

    # Accounts
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False),
        sa.Column('account_type', sa.String(50), default='CHECKING'),
        sa.Column('account_number_encrypted', sa.Text, nullable=True),
        sa.Column('routing_number', sa.String(20), nullable=True),
        sa.Column('rho_tenet_account_id', sa.String(200), nullable=True),
        sa.Column('rap_account_ref', sa.String(200), nullable=True),
        sa.Column('is_new_account', sa.Boolean, default=True),
        sa.Column('eng_ticket_key', sa.String(50), nullable=True),
        sa.Column('account_status', sa.String(50), default='PENDING_SETUP'),
        sa.Column('control_status', sa.String(50), default='BORROWER_CONTROL'),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lender_ach_account_encrypted', sa.Text, nullable=True),
        sa.Column('lender_ach_routing', sa.String(20), nullable=True),
        sa.Column('lender_wire_account_encrypted', sa.Text, nullable=True),
        sa.Column('lender_wire_routing', sa.String(20), nullable=True),
        sa.Column('sweep_cadence', sa.String(20), default='NEVER'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_accounts_daca_request_id', 'accounts', ['daca_request_id'])

    # Trigger Events
    op.create_table(
        'trigger_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('requested_by_email', sa.String(300), nullable=True),
        sa.Column('requested_by_name', sa.String(300), nullable=True),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lender_notified_webster', sa.Boolean, default=False),
        sa.Column('account_deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_verified', sa.Boolean, nullable=True),
        sa.Column('email_verification_method', sa.String(50), nullable=True),
        sa.Column('lender_external_bank_details_provided', sa.Boolean, default=False),
        sa.Column('jira_ticket_key', sa.String(50), nullable=True),
        sa.Column('verification_status', sa.String(50), default='PENDING'),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_by', sa.String(200), nullable=True),
        sa.Column('blocked_in_rap_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reactivated_after_block_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('control_change_from', sa.String(50), nullable=True),
        sa.Column('control_change_to', sa.String(50), nullable=True),
        sa.Column('lender_notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reversal_requested', sa.Boolean, default=False),
        sa.Column('reversal_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('request_document_url', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_trigger_events_daca_request_id', 'trigger_events', ['daca_request_id'])
    op.create_index('ix_trigger_events_account_id', 'trigger_events', ['account_id'])

    # Email Threads
    op.create_table(
        'email_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=True),
        sa.Column('gmail_thread_id', sa.String(200), unique=True, nullable=False),
        sa.Column('gmail_message_ids', postgresql.JSONB, nullable=True),
        sa.Column('subject', sa.Text, nullable=True),
        sa.Column('participants', postgresql.JSONB, nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sender', sa.String(300), nullable=True),
        sa.Column('last_snippet', sa.String(300), nullable=True),
        sa.Column('awaiting_response', sa.Boolean, default=False),
        sa.Column('response_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('slack_notification_sent', sa.Boolean, default=False),
        sa.Column('thread_status', sa.String(50), default='ACTIVE'),
        sa.Column('gmail_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_email_threads_daca_request_id', 'email_threads', ['daca_request_id'])
    op.create_index('ix_email_threads_gmail_thread_id', 'email_threads', ['gmail_thread_id'])

    # Email Drafts
    op.create_table(
        'email_drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=True),
        sa.Column('email_thread_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('email_threads.id'), nullable=True),
        sa.Column('draft_type', sa.String(50), nullable=False),
        sa.Column('trigger_event', sa.String(200), nullable=True),
        sa.Column('to_addresses', postgresql.JSONB, nullable=True),
        sa.Column('cc_addresses', postgresql.JSONB, nullable=True),
        sa.Column('subject', sa.Text, nullable=True),
        sa.Column('body_html', sa.Text, nullable=True),
        sa.Column('body_text', sa.Text, nullable=True),
        sa.Column('ai_model_used', sa.String(100), nullable=True),
        sa.Column('context_used', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(50), default='PENDING_REVIEW'),
        sa.Column('reviewed_by', sa.String(200), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('send_method', sa.String(50), nullable=True),
        sa.Column('gmail_message_id', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_email_drafts_daca_request_id', 'email_drafts', ['daca_request_id'])
    op.create_index('ix_email_drafts_email_thread_id', 'email_drafts', ['email_thread_id'])

    # Audit Logs
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=True),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(200), nullable=False),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('actor_id', sa.String(200), nullable=False),
        sa.Column('before_state', postgresql.JSONB, nullable=True),
        sa.Column('after_state', postgresql.JSONB, nullable=True),
        sa.Column('rationale', sa.Text, nullable=True),
        sa.Column('ops_manual_version', sa.String(200), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_audit_logs_daca_request_id', 'audit_logs', ['daca_request_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    # Human Review Items
    op.create_table(
        'human_review_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False),
        sa.Column('stage', sa.String(100), nullable=False),
        sa.Column('review_type', sa.String(50), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=True),
        sa.Column('agent_recommendation', sa.Text, nullable=True),
        sa.Column('agent_confidence', sa.Float, nullable=True),
        sa.Column('agent_name', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), default='PENDING'),
        sa.Column('assigned_to', sa.String(200), nullable=True),
        sa.Column('reviewed_by', sa.String(200), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_notes', sa.Text, nullable=True),
        sa.Column('sla_deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_human_review_items_daca_request_id', 'human_review_items', ['daca_request_id'])
    op.create_index('ix_human_review_items_status', 'human_review_items', ['status'])

    # Agent Executions
    op.create_table(
        'agent_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=True),
        sa.Column('agent_name', sa.String(100), nullable=False),
        sa.Column('task_description', sa.Text, nullable=True),
        sa.Column('input_payload', postgresql.JSONB, nullable=True),
        sa.Column('output_payload', postgresql.JSONB, nullable=True),
        sa.Column('status', sa.String(50), default='RUNNING'),
        sa.Column('confidence_score', sa.Float, nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('model_id', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('ops_manual_version', sa.String(200), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_agent_executions_daca_request_id', 'agent_executions', ['daca_request_id'])
    op.create_index('ix_agent_executions_agent_name', 'agent_executions', ['agent_name'])

    # Oversight Configs
    op.create_table(
        'oversight_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('stage', sa.String(100), nullable=True),
        sa.Column('mode', sa.String(30), nullable=False, default='HUMAN_OVERSIGHT'),
        sa.Column('confidence_threshold', sa.Float, default=0.85),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('updated_by', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('scope', 'stage', name='uq_oversight_scope_stage'),
    )

    # Notification Channels
    op.create_table(
        'notification_channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_id', sa.String(50), nullable=False),
        sa.Column('channel_name', sa.String(100), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean, default=False),
        sa.Column('updated_by', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('channel_id', 'notification_type', name='uq_channel_notif_type'),
    )

    # Auth Configs
    op.create_table(
        'auth_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('auth_mode', sa.String(20), nullable=False, default='NONE'),
        sa.Column('allowed_domain', sa.String(100), default='rho.co'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('updated_by', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Ops Manual Versions
    op.create_table(
        'ops_manual_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('drive_file_id', sa.String(200), nullable=False),
        sa.Column('drive_folder_id', sa.String(200)),
        sa.Column('drive_file_name', sa.String(500), nullable=False),
        sa.Column('version_label', sa.String(200), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_current', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_ops_manual_versions_is_current', 'ops_manual_versions', ['is_current'])

    # Documents
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False),
        sa.Column('document_type', sa.String(100), nullable=False),
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('google_drive_file_id', sa.String(200), nullable=True),
        sa.Column('google_drive_url', sa.Text, nullable=True),
        sa.Column('validation_status', sa.String(50), nullable=True),
        sa.Column('ai_extracted_data', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_documents_daca_request_id', 'documents', ['daca_request_id'])

    # Tasks
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('daca_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('daca_requests.id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('status', sa.String(50), default='PENDING'),
        sa.Column('assigned_to', sa.String(200), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_tasks_daca_request_id', 'tasks', ['daca_request_id'])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table('tasks')
    op.drop_table('documents')
    op.drop_table('ops_manual_versions')
    op.drop_table('auth_configs')
    op.drop_table('notification_channels')
    op.drop_table('oversight_configs')
    op.drop_table('agent_executions')
    op.drop_table('human_review_items')
    op.drop_table('audit_logs')
    op.drop_table('email_drafts')
    op.drop_table('email_threads')
    op.drop_table('trigger_events')
    op.drop_table('accounts')
    op.drop_table('agreements')
    op.drop_table('compliance_packages')
    op.drop_table('typeform_submissions')
    op.drop_table('daca_requests')
    op.drop_table('lenders')
    op.drop_table('borrowers')
