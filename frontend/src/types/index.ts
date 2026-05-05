/* ------------------------------------------------------------------ */
/*  TypeScript types matching the FastAPI backend Pydantic schemas     */
/* ------------------------------------------------------------------ */

/** 13 DACA lifecycle statuses (maps to JIRA board) */
export const DACA_STATUSES = [
  'Fraud Initial Review',
  'Typeform Sent',
  'Legal Redline Review',
  'Templates/Agreements Sent',
  'Pending Compliance Package Assembly',
  'Pre-Webster Review',
  'Docusign Sent',
  'Pending Final Setup',
  'Done',
  'Triggered',
  'Terminated',
  'Cancelled',
  'On Hold',
] as const;

export type DacaStatus = (typeof DACA_STATUSES)[number];

/** Stages that ALWAYS require human approval -- cannot be automated */
export const ALWAYS_HUMAN_STAGES: ReadonlySet<string> = new Set([
  'Fraud Initial Review',
  'Legal Redline Review',
  'Pre-Webster Review',
  'Triggered',
]);

/* ---------- DACA Request ---------- */

export interface DacaRequestListItem {
  id: string;
  external_ref: string;
  status: DacaStatus;
  priority: string;
  assigned_to: string | null;
  sla_deadline: string | null;
  jira_ticket_key: string | null;
  created_at: string;
  updated_at: string;
}

export interface DacaRequest {
  id: string;
  external_ref: string;
  borrower_id: string | null;
  lender_id: string | null;
  status: DacaStatus;
  previous_status: string | null;
  priority: string;
  source_channel: string;
  source_reference: string | null;
  typeform_token: string | null;
  jira_ticket_key: string | null;
  jira_status: string | null;
  assigned_to: string | null;
  sla_deadline: string | null;
  account_type_requested: string | null;
  docusign_envelope_id: string | null;
  has_redlines: boolean;
  redlines_approved_by: string | null;
  redlines_notes: string | null;
  salesforce_checklist: Record<string, unknown> | null;
  metadata_: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Borrower ---------- */

export interface Borrower {
  id: string;
  rho_id: string | null;
  legal_name: string;
  dba_name: string | null;
  entity_type: string | null;
  state_of_formation: string | null;
  address: Record<string, unknown> | null;
  primary_contact_name: string | null;
  primary_contact_email: string | null;
  primary_contact_phone: string | null;
  salesforce_account_id: string | null;
  has_rho_account: boolean;
  kyb_status: string;
  middesk_report_url: string | null;
  alloy_report_url: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Lender ---------- */

export interface Lender {
  id: string;
  institution_name: string;
  business_address: string | null;
  rep_count: number;
  representatives: unknown[] | null;
  primary_contact_email: string | null;
  primary_contact_phone: string | null;
  daca_type: string;
  created_at: string;
  updated_at: string;
}

/* ---------- Compliance Package ---------- */

export interface CompliancePackage {
  id: string;
  daca_request_id: string;
  typeform_pdf_attached: boolean;
  loan_agreement_uploaded: boolean;
  compliance_approved: boolean;
  middesk_report_uploaded: boolean;
  middesk_address_matches_rap: boolean;
  ein_tin_match_verified: boolean;
  alloy_report_verified: boolean;
  signatory_ubo_reports_verified: boolean;
  articles_of_incorporation_uploaded: boolean;
  name_change_docs_uploaded: boolean;
  division_of_corps_filing_uploaded: boolean;
  pre_webster_reviewed_by: string | null;
  pre_webster_reviewed_at: string | null;
  pre_webster_notes: string | null;
  webster_package_drive_id: string | null;
  webster_package_drive_url: string | null;
  webster_submission_date: string | null;
  webster_approval_status: string | null;
  webster_approved_at: string | null;
  webster_revisions_notes: string | null;
  created_at: string;
  updated_at: string;
}

/** Human-readable labels for the 11 compliance checklist booleans */
export const COMPLIANCE_CHECKLIST_ITEMS: { key: keyof CompliancePackage; label: string }[] = [
  { key: 'typeform_pdf_attached', label: 'Typeform PDF Attached' },
  { key: 'loan_agreement_uploaded', label: 'Loan Agreement Uploaded' },
  { key: 'compliance_approved', label: 'Compliance Approved' },
  { key: 'middesk_report_uploaded', label: 'Middesk Report Uploaded' },
  { key: 'middesk_address_matches_rap', label: 'Middesk Address Matches RAP' },
  { key: 'ein_tin_match_verified', label: 'EIN/TIN Match Verified' },
  { key: 'alloy_report_verified', label: 'Alloy Report Verified' },
  { key: 'signatory_ubo_reports_verified', label: 'Signatory/UBO Reports Verified' },
  { key: 'articles_of_incorporation_uploaded', label: 'Articles of Incorporation Uploaded' },
  { key: 'name_change_docs_uploaded', label: 'Name Change Docs Uploaded' },
  { key: 'division_of_corps_filing_uploaded', label: "Division of Corp's Filing Uploaded" },
];

/* ---------- Agreement ---------- */

export interface Agreement {
  id: string;
  daca_request_id: string;
  template_version: string;
  agreement_type: string;
  generated_document_drive_url: string | null;
  generated_document_drive_id: string | null;
  docusign_envelope_id: string | null;
  signing_status: string;
  borrower_signed_at: string | null;
  lender_signed_at: string | null;
  rho_signed_at: string | null;
  webster_signed_at: string | null;
  effective_date: string | null;
  has_redlines: boolean;
  redlines_approved_by_legal: boolean;
  redlines_approved_by_webster: boolean;
  redlines_notes: string | null;
  executed_document_drive_url: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Email Thread ---------- */

export interface EmailThread {
  id: string;
  daca_request_id: string;
  gmail_thread_id: string;
  subject: string | null;
  participants: string[] | null;
  last_message_at: string | null;
  last_sender: string | null;
  last_snippet: string | null;
  awaiting_response: boolean;
  slack_notification_sent: boolean;
  thread_status: string;
  gmail_url: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Email Draft ---------- */

export interface EmailDraft {
  id: string;
  daca_request_id: string;
  email_thread_id: string | null;
  draft_type: string;
  to_addresses: string[] | null;
  cc_addresses: string[] | null;
  subject: string;
  body_html: string;
  body_text: string | null;
  send_method: string;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  sent_at: string | null;
  gmail_message_id: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Human Review ---------- */

export interface HumanReview {
  id: string;
  daca_request_id: string;
  stage: string;
  review_type: string;
  payload: Record<string, unknown> | null;
  agent_recommendation: string | null;
  agent_confidence: number | null;
  agent_name: string | null;
  status: string;
  assigned_to: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  sla_deadline: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Audit Log ---------- */

export interface AuditLog {
  id: string;
  daca_request_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  actor_type: string;
  actor_id: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  rationale: string | null;
  ops_manual_version: string | null;
  metadata_: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

/* ---------- Oversight Config ---------- */

export interface OversightConfig {
  id: string;
  scope: string;
  stage: string | null;
  mode: 'FULL_AUTOMATION' | 'HUMAN_OVERSIGHT';
  confidence_threshold: number;
  enabled: boolean;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

/* ---------- Reports ---------- */

export interface PipelineReport {
  by_status: { status: string; count: number }[];
  total: number;
}

export interface SLAReport {
  total_tracked: number;
  breached: number;
  at_risk: number;
  on_track: number;
  compliance_rate: number;
  breaches: unknown[];
}

export interface VolumeDataPoint {
  day: string;
  count: number;
}

export interface HumanReviewReport {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  approval_rate: number;
}

export interface AgentPerformance {
  agent_name: string;
  total_runs: number;
  avg_confidence: number;
  avg_duration_ms: number;
}
