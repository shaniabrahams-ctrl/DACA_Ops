import { useEffect, useState } from 'react';
import { reviews as reviewApi } from '../api/client';
import type { HumanReview } from '../types';
import ReviewCard from '../components/ReviewCard';

export default function ReviewQueue() {
  const [items, setItems] = useState<HumanReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('PENDING');

  const fetchItems = () => {
    setLoading(true);
    setError(null);
    reviewApi
      .list({ status: statusFilter || undefined, limit: 100 })
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchItems();
  }, [statusFilter]);

  const handleApprove = async (id: string, notes?: string) => {
    await reviewApi.approve(id, notes);
    fetchItems();
  };

  const handleReject = async (id: string, notes?: string) => {
    await reviewApi.reject(id, notes);
    fetchItems();
  };

  const handleReturn = async (id: string, notes?: string) => {
    await reviewApi.returnForRevision(id, notes);
    fetchItems();
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Review Queue</h1>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-500">{items.length} item(s)</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field w-40"
          >
            <option value="PENDING">Pending</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">Rejected</option>
            <option value="">All</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-400">Loading review items...</div>
      ) : items.length === 0 ? (
        <div className="py-20 text-center text-gray-400">
          No review items matching the selected filter.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <ReviewCard
              key={item.id}
              review={item}
              onApprove={handleApprove}
              onReject={handleReject}
              onReturn={handleReturn}
            />
          ))}
        </div>
      )}
    </div>
  );
}
