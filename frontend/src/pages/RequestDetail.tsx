import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  dacaRequests,
  borrowers as borrowerApi,
  lenders as lenderApi,
  compliance as complianceApi,
  emailThreads as emailThreadApi,
  agreements as agreementApi,
} from '../api/client';
import type {
  DacaRequest,
  Borrower,
  Lender,
  CompliancePackage,
  EmailThread,
  Agreement,
  AuditLog,
} from '../types';
import { COMPLIANCE_CHECKLIST_ITEMS } from '../types';
import StatusBadge from '../components/StatusBadge';
import SLAIndicator from '../components/SLAIndicator';
import TimelineEvent from '../components/TimelineEvent';

type Tab = 'overview' | 'emails' | 'compliance' | 'agreement' | 'timeline';

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [request, setRequest] = useState<DacaRequest | null>(null);
  const [borrower, setBorrower] = useState<Borrower | null>(null);
  const [lender, setLender] = useState<Lender | null>(null);
  const [compliancePkg, setCompliancePkg] = useState<CompliancePackage | null>(null);
  const [emailThreads, setEmailThreads] = useState<EmailThread[]>([]);
  const [agreement, setAgreement] = useState<Agreement | null>(null);
  const [timeline, setTimeline] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);

    dacaRequests
      .get(id)
      .then(async (req) => {
        setRequest(req);

        // Fetch related resources in parallel -- silently skip if not found
        const [bResult, lResult, cResult, etResult, agResult, tlResult] =
          await Promise.allSettled([
            req.borrower_id ? borrowerApi.get(req.borrower_id) : Promise.resolve(null),
            req.lender_id ? lenderApi.get(req.lender_id) : Promise.resolve(null),
            complianceApi.get(id),
            emailThreadApi.list({ daca_request_id: id }),
            agreementApi.getByRequest(id).catch(() => null),
            dacaRequests.timeline(id),
          ]);

        if (bResult.status === 'fulfilled') setBorrower(bResult.value);
        if (lResult.status === 'fulfilled') setLender(lResult.value);
        if (cResult.status === 'fulfilled') setCompliancePkg(cResult.value);
        if (etResult.status === 'fulfilled') setEmailThreads(etResult.value);
        if (agResult.status === 'fulfilled') setAgreement(agResult.value);
        if (tlResult.status === 'fulfilled') setTimeline(tlResult.value);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="py-20 text-center text-gray-400">Loading request...</div>;
  }

  if (error || !request) {
    return (
      <div className="py-20 text-center text-red-600">
        {error ?? 'Request not found'}
      </div>
    );
  }

  const TABS: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'emails', label: `Emails (${emailThreads.length})` },
    { key: 'compliance', label: 'Compliance' },
    { key: 'agreement', label: 'Agreement' },
    { key: 'timeline', label: `Timeline (${timeline.length})` },
  ];

  return (
    <div>
      {/* Breadcrumb + header */}
      <div className="mb-6">
        <Link to="/pipeline" className="text-sm text-rho-600 hover:underline">
          &larr; Pipeline
        </Link>
        <div className="mt-2 flex items-center gap-4">
          <h1 className="text-2xl font-bold text-gray-900">{request.external_ref}</h1>
          <StatusBadge status={request.status} />
          <SLAIndicator deadline={request.sla_deadline} />
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`whitespace-nowrap border-b-2 pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.key
                  ? 'border-rho-600 text-rho-600'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <OverviewTab request={request} borrower={borrower} lender={lender} />
      )}
      {activeTab === 'emails' && <EmailsTab threads={emailThreads} />}
      {activeTab === 'compliance' && (
        <ComplianceTab pkg={compliancePkg} requestId={request.id} />
      )}
      {activeTab === 'agreement' && <AgreementTab agreement={agreement} />}
      {activeTab === 'timeline' && <TimelineTab events={timeline} />}
    </div>
  );
}

/* ================================================================ */
/*  OVERVIEW TAB                                                     */
/* ================================================================ */

function OverviewTab({
  request,
  borrower,
  lender,
}: {
  request: DacaRequest;
  borrower: Borrower | null;
  lender: Lender | null;
}) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Key Fields */}
      <div className="card">
        <h2 className="mb-4 text-base font-semibold text-gray-900">Request Details</h2>
        <dl className="space-y-3 text-sm">
          <Field label="External Ref" value={request.external_ref} />
          <Field label="Status" value={request.status} />
          <Field label="Previous Status" value={request.previous_status} />
          <Field label="Priority" value={request.priority} />
          <Field label="Source" value={`${request.source_channel}${request.source_reference ? ` (${request.source_reference})` : ''}`} />
          <Field label="Assigned To" value={request.assigned_to} />
          <Field label="JIRA" value={request.jira_ticket_key} />
          <Field label="JIRA Status" value={request.jira_status} />
          <Field label="Account Type" value={request.account_type_requested} />
          <Field label="DocuSign Envelope" value={request.docusign_envelope_id} />
          <Field label="Has Redlines" value={request.has_redlines ? 'Yes' : 'No'} />
          {request.has_redlines && (
            <>
              <Field label="Redlines Approved By" value={request.redlines_approved_by} />
              <Field label="Redlines Notes" value={request.redlines_notes} />
            </>
          )}
          <Field
            label="Created"
            value={new Date(request.created_at).toLocaleString()}
          />
          <Field
            label="Updated"
            value={new Date(request.updated_at).toLocaleString()}
          />
        </dl>
      </div>

      {/* Parties */}
      <div className="space-y-6">
        <div className="card">
          <h2 className="mb-4 text-base font-semibold text-gray-900">Borrower</h2>
          {borrower ? (
            <dl className="space-y-2 text-sm">
              <Field label="Legal Name" value={borrower.legal_name} />
              <Field label="DBA" value={borrower.dba_name} />
              <Field label="Entity Type" value={borrower.entity_type} />
              <Field label="Contact" value={borrower.primary_contact_name} />
              <Field label="Email" value={borrower.primary_contact_email} />
              <Field label="KYB Status" value={borrower.kyb_status} />
              <Field label="Has Rho Account" value={borrower.has_rho_account ? 'Yes' : 'No'} />
            </dl>
          ) : (
            <p className="text-sm text-gray-400">No borrower linked.</p>
          )}
        </div>

        <div className="card">
          <h2 className="mb-4 text-base font-semibold text-gray-900">Lender</h2>
          {lender ? (
            <dl className="space-y-2 text-sm">
              <Field label="Institution" value={lender.institution_name} />
              <Field label="Address" value={lender.business_address} />
              <Field label="DACA Type" value={lender.daca_type} />
              <Field label="Email" value={lender.primary_contact_email} />
              <Field label="Rep Count" value={String(lender.rep_count)} />
            </dl>
          ) : (
            <p className="text-sm text-gray-400">No lender linked.</p>
          )}
        </div>
      </div>

      {/* Salesforce Checklist */}
      {request.salesforce_checklist && (
        <div className="card lg:col-span-2">
          <h2 className="mb-4 text-base font-semibold text-gray-900">
            Salesforce Checklist
          </h2>
          <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
            {Object.entries(request.salesforce_checklist).map(([key, val]) => (
              <div key={key} className="flex items-center gap-2">
                <CheckIcon checked={Boolean((val as Record<string, unknown>)?.value)} />
                <span className="text-gray-700">{key.replace(/_/g, ' ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ================================================================ */
/*  EMAILS TAB                                                       */
/* ================================================================ */

function EmailsTab({ threads }: { threads: EmailThread[] }) {
  if (threads.length === 0) {
    return <div className="py-10 text-center text-gray-400">No email threads found.</div>;
  }

  return (
    <div className="space-y-4">
      {threads.map((t) => (
        <div key={t.id} className="card flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-gray-900">
                {t.subject ?? '(No subject)'}
              </h3>
              {t.awaiting_response && (
                <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                  Awaiting Response
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-gray-500">
              {t.participants?.join(', ') ?? 'No participants'}
            </p>
            {t.last_snippet && (
              <p className="mt-2 text-sm text-gray-600 line-clamp-2">{t.last_snippet}</p>
            )}
          </div>
          <div className="ml-4 flex flex-col items-end gap-1 text-xs text-gray-400">
            <span>{t.thread_status}</span>
            {t.last_message_at && (
              <span>{new Date(t.last_message_at).toLocaleString()}</span>
            )}
            {t.gmail_url && (
              <a
                href={t.gmail_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-rho-600 hover:underline"
              >
                Open in Gmail
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ================================================================ */
/*  COMPLIANCE TAB                                                   */
/* ================================================================ */

function ComplianceTab({
  pkg,
  requestId,
}: {
  pkg: CompliancePackage | null;
  requestId: string;
}) {
  const [compPkg, setCompPkg] = useState(pkg);
  const [saving, setSaving] = useState(false);

  const handleToggle = async (key: string, currentValue: boolean) => {
    if (!compPkg) return;
    setSaving(true);
    try {
      const updated = await complianceApi.update(compPkg.id, {
        [key]: !currentValue,
      } as Partial<CompliancePackage>);
      setCompPkg(updated);
    } catch {
      // silently fail for now
    } finally {
      setSaving(false);
    }
  };

  if (!compPkg) {
    return <div className="py-10 text-center text-gray-400">No compliance package found for this request.</div>;
  }

  const completedCount = COMPLIANCE_CHECKLIST_ITEMS.filter(
    (item) => compPkg[item.key] === true,
  ).length;

  return (
    <div className="space-y-6">
      {/* Progress */}
      <div className="card">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold text-gray-900">Compliance Checklist</h2>
          <span className="text-sm text-gray-500">
            {completedCount} / {COMPLIANCE_CHECKLIST_ITEMS.length} completed
          </span>
        </div>
        <div className="h-2 rounded-full bg-gray-200">
          <div
            className="h-2 rounded-full bg-sla-green transition-all"
            style={{
              width: `${Math.round((completedCount / COMPLIANCE_CHECKLIST_ITEMS.length) * 100)}%`,
            }}
          />
        </div>
      </div>

      {/* Checklist items */}
      <div className="card space-y-3">
        {COMPLIANCE_CHECKLIST_ITEMS.map((item) => {
          const checked = compPkg[item.key] === true;
          return (
            <label
              key={item.key}
              className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 hover:bg-gray-50"
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={saving}
                onChange={() => handleToggle(item.key, checked)}
                className="h-4 w-4 rounded border-gray-300 text-rho-600 focus:ring-rho-500"
              />
              <span className={`text-sm ${checked ? 'text-gray-900' : 'text-gray-500'}`}>
                {item.label}
              </span>
            </label>
          );
        })}
      </div>

      {/* Pre-Webster & Webster details */}
      <div className="card">
        <h2 className="mb-4 text-base font-semibold text-gray-900">
          Webster Submission
        </h2>
        <dl className="space-y-2 text-sm">
          <Field label="Pre-Webster Reviewed By" value={compPkg.pre_webster_reviewed_by} />
          <Field
            label="Pre-Webster Reviewed At"
            value={compPkg.pre_webster_reviewed_at ? new Date(compPkg.pre_webster_reviewed_at).toLocaleString() : null}
          />
          <Field label="Pre-Webster Notes" value={compPkg.pre_webster_notes} />
          <Field label="Webster Drive URL" value={compPkg.webster_package_drive_url} />
          <Field label="Submission Date" value={compPkg.webster_submission_date} />
          <Field label="Approval Status" value={compPkg.webster_approval_status} />
          <Field label="Revision Notes" value={compPkg.webster_revisions_notes} />
        </dl>
      </div>
    </div>
  );
}

/* ================================================================ */
/*  AGREEMENT TAB                                                    */
/* ================================================================ */

function AgreementTab({ agreement: ag }: { agreement: Agreement | null }) {
  if (!ag) {
    return <div className="py-10 text-center text-gray-400">No agreement found.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">
            {ag.agreement_type} Agreement (v{ag.template_version})
          </h3>
          <StatusBadge status={ag.signing_status} />
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <Field label="DocuSign Envelope" value={ag.docusign_envelope_id} />
          <Field label="Effective Date" value={ag.effective_date} />
          <Field label="Borrower Signed" value={ag.borrower_signed_at ? new Date(ag.borrower_signed_at).toLocaleString() : null} />
          <Field label="Lender Signed" value={ag.lender_signed_at ? new Date(ag.lender_signed_at).toLocaleString() : null} />
          <Field label="Rho Signed" value={ag.rho_signed_at ? new Date(ag.rho_signed_at).toLocaleString() : null} />
          <Field label="Webster Signed" value={ag.webster_signed_at ? new Date(ag.webster_signed_at).toLocaleString() : null} />
          <Field label="Has Redlines" value={ag.has_redlines ? 'Yes' : 'No'} />
          {ag.has_redlines && (
            <>
              <Field label="Legal Approved Redlines" value={ag.redlines_approved_by_legal ? 'Yes' : 'No'} />
              <Field label="Webster Approved Redlines" value={ag.redlines_approved_by_webster ? 'Yes' : 'No'} />
              <Field label="Redlines Notes" value={ag.redlines_notes} />
            </>
          )}
        </dl>
        {(ag.generated_document_drive_url || ag.executed_document_drive_url) && (
          <div className="mt-4 flex gap-3">
            {ag.generated_document_drive_url && (
              <a
                href={ag.generated_document_drive_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary text-xs"
              >
                View Generated Doc
              </a>
            )}
            {ag.executed_document_drive_url && (
              <a
                href={ag.executed_document_drive_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary text-xs"
              >
                View Executed Doc
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ================================================================ */
/*  TIMELINE TAB                                                     */
/* ================================================================ */

function TimelineTab({ events }: { events: AuditLog[] }) {
  if (events.length === 0) {
    return <div className="py-10 text-center text-gray-400">No timeline events found.</div>;
  }

  return (
    <div className="card">
      {events.map((ev) => (
        <TimelineEvent key={ev.id} event={ev} />
      ))}
    </div>
  );
}

/* ================================================================ */
/*  Shared helper components                                         */
/* ================================================================ */

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-right font-medium text-gray-900">{value ?? '--'}</dd>
    </div>
  );
}

function CheckIcon({ checked }: { checked: boolean }) {
  return checked ? (
    <svg className="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
        clipRule="evenodd"
      />
    </svg>
  ) : (
    <svg className="h-5 w-5 text-gray-300" fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
        clipRule="evenodd"
      />
    </svg>
  );
}
