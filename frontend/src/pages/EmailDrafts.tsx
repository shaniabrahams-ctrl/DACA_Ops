import { useEffect, useState } from 'react';
import { emailDrafts as draftApi } from '../api/client';
import type { EmailDraft } from '../types';
import StatusBadge from '../components/StatusBadge';

export default function EmailDrafts() {
  const [drafts, setDrafts] = useState<EmailDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchDrafts = () => {
    setLoading(true);
    setError(null);
    draftApi
      .list({ status: statusFilter || undefined })
      .then(setDrafts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDrafts();
  }, [statusFilter]);

  const handleSend = async (id: string) => {
    if (!window.confirm('Are you sure you want to send this email?')) return;
    try {
      await draftApi.send(id);
      fetchDrafts();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send');
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Email Drafts</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{drafts.length} draft(s)</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-40"
          >
            <option value="">All</option>
            <option value="DRAFT">Draft</option>
            <option value="SENT">Sent</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-400">Loading email drafts...</div>
      ) : drafts.length === 0 ? (
        <div className="py-20 text-center text-gray-400">No email drafts found.</div>
      ) : (
        <div className="space-y-4">
          {drafts.map((draft) => {
            const isExpanded = expandedId === draft.id;
            return (
              <div key={draft.id} className="card">
                {/* Header row */}
                <div className="flex items-start justify-between">
                  <div
                    className="flex-1 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : draft.id)}
                  >
                    <div className="flex items-center gap-3">
                      <h3 className="text-sm font-medium text-gray-900">
                        {draft.subject}
                      </h3>
                      <StatusBadge status={draft.status} />
                      <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                        {draft.draft_type}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      To: {draft.to_addresses?.join(', ') ?? 'N/A'}
                      {draft.cc_addresses?.length
                        ? ` | CC: ${draft.cc_addresses.join(', ')}`
                        : ''}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-400">
                      Method: {draft.send_method} &middot; Created:{' '}
                      {new Date(draft.created_at).toLocaleString()}
                      {draft.sent_at
                        ? ` | Sent: ${new Date(draft.sent_at).toLocaleString()}`
                        : ''}
                    </p>
                  </div>
                  <div className="ml-4 flex gap-2">
                    {draft.status !== 'SENT' && (
                      <button
                        onClick={() => handleSend(draft.id)}
                        className="btn-primary text-xs"
                      >
                        Send
                      </button>
                    )}
                  </div>
                </div>

                {/* Expanded body */}
                {isExpanded && (
                  <div className="mt-4 border-t border-gray-100 pt-4">
                    <div
                      className="prose prose-sm max-w-none text-gray-700"
                      dangerouslySetInnerHTML={{ __html: draft.body_html }}
                    />
                    {draft.reviewed_by && (
                      <p className="mt-3 text-xs text-gray-400">
                        Reviewed by: {draft.reviewed_by}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
