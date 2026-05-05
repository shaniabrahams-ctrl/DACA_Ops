import { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { dacaRequests } from '../api/client';
import type { DacaRequestListItem } from '../types';
import { DACA_STATUSES } from '../types';
import StatusBadge from '../components/StatusBadge';
import SLAIndicator from '../components/SLAIndicator';

type SortKey = keyof DacaRequestListItem;
type SortDir = 'asc' | 'desc';

export default function Pipeline() {
  const [items, setItems] = useState<DacaRequestListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  useEffect(() => {
    setLoading(true);
    setError(null);
    dacaRequests
      .list({
        status: filterStatus || undefined,
        priority: filterPriority || undefined,
        limit: 200,
      })
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filterStatus, filterPriority]);

  const sorted = useMemo(() => {
    const copy = [...items];
    copy.sort((a, b) => {
      const aVal = a[sortKey] ?? '';
      const bVal = b[sortKey] ?? '';
      if (aVal < bVal) return sortDir === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    return copy;
  }, [items, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const SortArrow = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return null;
    return <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>;
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">DACA Pipeline</h1>
        <div className="flex gap-3">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input-field w-56"
          >
            <option value="">All Statuses</option>
            {DACA_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="input-field w-36"
          >
            <option value="">All Priorities</option>
            <option value="NORMAL">Normal</option>
            <option value="HIGH">High</option>
            <option value="URGENT">Urgent</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-400">Loading requests...</div>
      ) : sorted.length === 0 ? (
        <div className="py-20 text-center text-gray-400">No requests found.</div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <Th onClick={() => toggleSort('external_ref')}>
                  # <SortArrow col="external_ref" />
                </Th>
                <Th onClick={() => toggleSort('status')}>
                  Status <SortArrow col="status" />
                </Th>
                <Th onClick={() => toggleSort('priority')}>
                  Priority <SortArrow col="priority" />
                </Th>
                <Th onClick={() => toggleSort('sla_deadline')}>
                  SLA <SortArrow col="sla_deadline" />
                </Th>
                <Th onClick={() => toggleSort('assigned_to')}>
                  Assigned To <SortArrow col="assigned_to" />
                </Th>
                <Th onClick={() => toggleSort('jira_ticket_key')}>
                  JIRA <SortArrow col="jira_ticket_key" />
                </Th>
                <Th onClick={() => toggleSort('created_at')}>
                  Created <SortArrow col="created_at" />
                </Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.map((req) => (
                <tr key={req.id} className="hover:bg-gray-50 transition-colors">
                  <td className="table-cell font-medium">
                    <Link
                      to={`/requests/${req.id}`}
                      className="text-rho-600 hover:underline"
                    >
                      {req.external_ref}
                    </Link>
                  </td>
                  <td className="table-cell">
                    <StatusBadge status={req.status} />
                  </td>
                  <td className="table-cell">
                    <PriorityBadge priority={req.priority} />
                  </td>
                  <td className="table-cell">
                    <SLAIndicator deadline={req.sla_deadline} />
                  </td>
                  <td className="table-cell">{req.assigned_to ?? '--'}</td>
                  <td className="table-cell text-xs text-gray-500">
                    {req.jira_ticket_key ?? '--'}
                  </td>
                  <td className="table-cell text-xs text-gray-500">
                    {new Date(req.created_at).toLocaleDateString()}
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

/* ---------- Helper components ---------- */

function Th({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <th
      className="table-header cursor-pointer select-none hover:text-gray-700"
      onClick={onClick}
    >
      {children}
    </th>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    URGENT: 'bg-red-100 text-red-800',
    HIGH: 'bg-orange-100 text-orange-800',
    NORMAL: 'bg-gray-100 text-gray-700',
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        colors[priority] ?? colors.NORMAL
      }`}
    >
      {priority}
    </span>
  );
}
