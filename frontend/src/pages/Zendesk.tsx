import { useEffect, useState } from 'react';

interface ZendeskTicket {
  id: string;
  zendesk_ticket_id: number;
  daca_request_id: string | null;
  subject: string | null;
  description: string | null;
  status: string | null;
  priority: string | null;
  ticket_type: string | null;
  requester_email: string | null;
  requester_name: string | null;
  assignee_email: string | null;
  tags: string[] | null;
  match_reason: string;
  matched_daca_ref: string | null;
  web_url: string | null;
  zendesk_created_at: string | null;
  zendesk_updated_at: string | null;
  last_synced_at: string | null;
  slack_notification_sent: boolean;
  last_comment_count: number;
  created_at: string;
  updated_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-blue-100 text-blue-800',
  open: 'bg-amber-100 text-amber-800',
  pending: 'bg-purple-100 text-purple-800',
  hold: 'bg-gray-200 text-gray-700',
  solved: 'bg-green-100 text-green-800',
  closed: 'bg-gray-100 text-gray-600',
};

const MATCH_LABELS: Record<string, string> = {
  DACA_EMAIL_IN_THREAD: 'daca@rho.co in thread',
  DACA_KEYWORD: 'mentions "DACA"',
  DACA_REF_MATCH: 'DACA ref in subject',
};

export default function Zendesk() {
  const [tickets, setTickets] = useState<ZendeskTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterMatch, setFilterMatch] = useState('');
  const [syncing, setSyncing] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (filterStatus) qs.set('status', filterStatus);
      if (filterMatch) qs.set('match_reason', filterMatch);
      const res = await fetch(`/api/v1/zendesk-tickets${qs.toString() ? `?${qs}` : ''}`);
      if (!res.ok) throw new Error(`API ${res.status}`);
      setTickets(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterStatus, filterMatch]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await fetch('/api/v1/sync/zendesk', { method: 'POST' });
      const data = await res.json();
      if (data.result) {
        alert(
          `Zendesk sync complete: ${data.result.created} new, ${data.result.updated} updated, ${data.result.notified} Slack alerts sent.`,
        );
      }
      await load();
    } catch (e) {
      alert(`Sync failed: ${e instanceof Error ? e.message : 'unknown'}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Zendesk — DACA Mentions</h1>
          <p className="mt-1 text-sm text-gray-500">
            Tickets where daca@rho.co is involved or "DACA" is mentioned. Slack alerts to
            #daca-ops are sent on new mentions.
          </p>
        </div>
        <div className="flex gap-3">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input-field w-40"
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="open">Open</option>
            <option value="pending">Pending</option>
            <option value="hold">Hold</option>
            <option value="solved">Solved</option>
            <option value="closed">Closed</option>
          </select>
          <select
            value={filterMatch}
            onChange={(e) => setFilterMatch(e.target.value)}
            className="input-field w-56"
          >
            <option value="">All Match Reasons</option>
            <option value="DACA_EMAIL_IN_THREAD">daca@rho.co in thread</option>
            <option value="DACA_KEYWORD">Mentions "DACA"</option>
            <option value="DACA_REF_MATCH">DACA ref in subject</option>
          </select>
          <button onClick={handleSync} disabled={syncing} className="btn-primary">
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-400">Loading tickets...</div>
      ) : tickets.length === 0 ? (
        <div className="card py-20 text-center text-gray-500">
          <p className="font-medium">No Zendesk tickets pulled in yet.</p>
          <p className="mt-1 text-sm">
            Add ZENDESK_API_TOKEN and ZENDESK_EMAIL to your .env file, then click Sync Now.
          </p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="table-header">Ticket #</th>
                <th className="table-header">Subject</th>
                <th className="table-header">Requester</th>
                <th className="table-header">Status</th>
                <th className="table-header">Match Reason</th>
                <th className="table-header">DACA Ref</th>
                <th className="table-header">Updated</th>
                <th className="table-header" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tickets.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="table-cell font-medium">#{t.zendesk_ticket_id}</td>
                  <td className="table-cell">
                    <div className="max-w-md truncate" title={t.subject ?? ''}>
                      {t.subject ?? '(no subject)'}
                    </div>
                  </td>
                  <td className="table-cell text-xs">
                    <div>{t.requester_name ?? '--'}</div>
                    <div className="text-gray-400">{t.requester_email ?? ''}</div>
                  </td>
                  <td className="table-cell">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_COLORS[t.status ?? ''] ?? 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {t.status ?? 'unknown'}
                    </span>
                  </td>
                  <td className="table-cell text-xs text-gray-600">
                    {MATCH_LABELS[t.match_reason] ?? t.match_reason}
                  </td>
                  <td className="table-cell text-xs">
                    {t.matched_daca_ref ? (
                      <a
                        href={`/requests/${t.daca_request_id}`}
                        className="text-rho-600 hover:underline"
                      >
                        {t.matched_daca_ref}
                      </a>
                    ) : (
                      <span className="text-gray-300">--</span>
                    )}
                  </td>
                  <td className="table-cell text-xs text-gray-500">
                    {t.zendesk_updated_at
                      ? new Date(t.zendesk_updated_at).toLocaleString()
                      : '--'}
                  </td>
                  <td className="table-cell">
                    {t.web_url && (
                      <a
                        href={t.web_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-rho-600 hover:underline"
                      >
                        Open
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
