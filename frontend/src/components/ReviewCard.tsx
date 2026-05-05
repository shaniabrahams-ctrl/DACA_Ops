import { useState } from 'react';
import type { HumanReview } from '../types';
import StatusBadge from './StatusBadge';

interface Props {
  review: HumanReview;
  onApprove: (id: string, notes?: string) => Promise<void>;
  onReject: (id: string, notes?: string) => Promise<void>;
  onReturn: (id: string, notes?: string) => Promise<void>;
}

export default function ReviewCard({ review, onApprove, onReject, onReturn }: Props) {
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAction = async (action: 'approve' | 'reject' | 'return') => {
    setLoading(true);
    try {
      if (action === 'approve') await onApprove(review.id, notes || undefined);
      else if (action === 'reject') await onReject(review.id, notes || undefined);
      else await onReturn(review.id, notes || undefined);
    } finally {
      setLoading(false);
    }
  };

  const confidence = review.agent_confidence;

  return (
    <div className="card space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">{review.stage}</h3>
          <p className="mt-0.5 text-xs text-gray-500">
            Type: {review.review_type} &middot; Agent: {review.agent_name ?? 'N/A'}
          </p>
        </div>
        <StatusBadge status={review.status} />
      </div>

      {/* Recommendation + Confidence */}
      {review.agent_recommendation && (
        <div className="rounded-md border border-gray-100 bg-gray-50 p-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Agent Recommendation</p>
          <p className="mt-1 text-sm text-gray-800">{review.agent_recommendation}</p>
        </div>
      )}

      {confidence !== null && confidence !== undefined && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Confidence Score
          </p>
          <div className="flex items-center gap-3">
            <div className="h-2 flex-1 rounded-full bg-gray-200">
              <div
                className={`h-2 rounded-full ${
                  confidence >= 0.85
                    ? 'bg-sla-green'
                    : confidence >= 0.6
                      ? 'bg-sla-amber'
                      : 'bg-sla-red'
                }`}
                style={{ width: `${Math.round(confidence * 100)}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-700">
              {Math.round(confidence * 100)}%
            </span>
          </div>
        </div>
      )}

      {/* Assigned / SLA */}
      <div className="flex gap-6 text-xs text-gray-500">
        <span>Assigned: {review.assigned_to ?? 'Unassigned'}</span>
        {review.sla_deadline && (
          <span>
            SLA: {new Date(review.sla_deadline).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Notes input + action buttons (only for PENDING items) */}
      {review.status === 'PENDING' && (
        <>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Review notes (optional)..."
            className="input-field resize-none"
            rows={2}
          />
          <div className="flex gap-2">
            <button
              onClick={() => handleAction('approve')}
              disabled={loading}
              className="btn-success flex-1"
            >
              Approve
            </button>
            <button
              onClick={() => handleAction('reject')}
              disabled={loading}
              className="btn-danger flex-1"
            >
              Reject
            </button>
            <button
              onClick={() => handleAction('return')}
              disabled={loading}
              className="btn-secondary flex-1"
            >
              Return
            </button>
          </div>
        </>
      )}

      {/* For non-PENDING: show review notes if present */}
      {review.status !== 'PENDING' && review.review_notes && (
        <div className="text-sm text-gray-600">
          <span className="font-medium">Review Notes:</span> {review.review_notes}
        </div>
      )}
    </div>
  );
}
