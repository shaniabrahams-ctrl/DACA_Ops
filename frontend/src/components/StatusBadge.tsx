import type { DacaStatus } from '../types';

/** Map each DACA status to a color class pair (bg + text). */
const STATUS_COLORS: Record<string, string> = {
  'Fraud Initial Review': 'bg-red-100 text-red-800',
  'Typeform Sent': 'bg-blue-100 text-blue-800',
  'Legal Redline Review': 'bg-orange-100 text-orange-800',
  'Templates/Agreements Sent': 'bg-sky-100 text-sky-800',
  'Pending Compliance Package Assembly': 'bg-yellow-100 text-yellow-800',
  'Pre-Webster Review': 'bg-purple-100 text-purple-800',
  'Docusign Sent': 'bg-indigo-100 text-indigo-800',
  'Pending Final Setup': 'bg-cyan-100 text-cyan-800',
  Done: 'bg-green-100 text-green-800',
  Triggered: 'bg-red-100 text-red-800',
  Terminated: 'bg-gray-200 text-gray-800',
  Cancelled: 'bg-gray-100 text-gray-600',
  'On Hold': 'bg-amber-100 text-amber-800',
};

interface Props {
  status: DacaStatus | string;
}

export default function StatusBadge({ status }: Props) {
  const colors = STATUS_COLORS[status] ?? 'bg-gray-100 text-gray-700';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors}`}
    >
      {status}
    </span>
  );
}
