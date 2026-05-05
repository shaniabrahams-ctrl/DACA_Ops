import { useEffect, useState } from 'react';
import { reports as reportsApi } from '../api/client';
import type {
  PipelineReport,
  SLAReport,
  VolumeDataPoint,
  HumanReviewReport,
  AgentPerformance,
} from '../types';

export default function Reports() {
  const [pipeline, setPipeline] = useState<PipelineReport | null>(null);
  const [sla, setSla] = useState<SLAReport | null>(null);
  const [volume, setVolume] = useState<VolumeDataPoint[]>([]);
  const [reviewStats, setReviewStats] = useState<HumanReviewReport | null>(null);
  const [agentPerf, setAgentPerf] = useState<AgentPerformance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    Promise.allSettled([
      reportsApi.pipeline().then(setPipeline),
      reportsApi.sla().then(setSla),
      reportsApi.volume(30).then(setVolume),
      reportsApi.humanReview().then(setReviewStats),
      reportsApi.agentPerformance().then(setAgentPerf),
    ])
      .then((results) => {
        const failed = results.filter((r) => r.status === 'rejected');
        if (failed.length === results.length) {
          setError('Failed to load reports. Make sure the API is running.');
        }
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="py-20 text-center text-gray-400">Loading reports...</div>;
  }

  if (error) {
    return (
      <div className="py-20 text-center text-red-600">{error}</div>
    );
  }

  const maxVolumeCount = Math.max(...volume.map((v) => v.count), 1);

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Reports</h1>

      {/* KPI Cards Row */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total Requests"
          value={pipeline?.total ?? 0}
          color="text-rho-600"
        />
        <KpiCard
          label="SLA Compliance"
          value={sla ? `${sla.compliance_rate}%` : '--'}
          color="text-sla-green"
        />
        <KpiCard
          label="Pending Reviews"
          value={reviewStats?.pending ?? 0}
          color="text-sla-amber"
        />
        <KpiCard
          label="SLA Breaches"
          value={sla?.breached ?? 0}
          color="text-sla-red"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Pipeline chart -- horizontal bar chart */}
        {pipeline && (
          <section className="card">
            <h2 className="mb-4 text-base font-semibold text-gray-900">
              Requests by Status
            </h2>
            <div className="space-y-2">
              {pipeline.by_status
                .sort((a, b) => b.count - a.count)
                .map((item) => {
                  const pct =
                    pipeline.total > 0
                      ? Math.round((item.count / pipeline.total) * 100)
                      : 0;
                  return (
                    <div key={item.status}>
                      <div className="mb-1 flex justify-between text-xs">
                        <span className="text-gray-700 truncate max-w-[200px]">
                          {item.status}
                        </span>
                        <span className="font-medium text-gray-900">
                          {item.count} ({pct}%)
                        </span>
                      </div>
                      <div className="h-3 w-full rounded-full bg-gray-100">
                        <div
                          className="h-3 rounded-full bg-rho-600 transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </section>
        )}

        {/* SLA Compliance breakdown */}
        {sla && (
          <section className="card">
            <h2 className="mb-4 text-base font-semibold text-gray-900">
              SLA Compliance
            </h2>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="rounded-lg bg-green-50 p-4">
                <p className="text-2xl font-bold text-sla-green">{sla.on_track}</p>
                <p className="text-xs text-gray-500">On Track</p>
              </div>
              <div className="rounded-lg bg-amber-50 p-4">
                <p className="text-2xl font-bold text-sla-amber">{sla.at_risk}</p>
                <p className="text-xs text-gray-500">At Risk</p>
              </div>
              <div className="rounded-lg bg-red-50 p-4">
                <p className="text-2xl font-bold text-sla-red">{sla.breached}</p>
                <p className="text-xs text-gray-500">Breached</p>
              </div>
            </div>
            <div className="mt-4 text-center">
              <p className="text-sm text-gray-500">
                Overall compliance rate:{' '}
                <span className="font-semibold text-gray-900">{sla.compliance_rate}%</span>
              </p>
            </div>
          </section>
        )}

        {/* Volume chart -- simple bar chart */}
        {volume.length > 0 && (
          <section className="card lg:col-span-2">
            <h2 className="mb-4 text-base font-semibold text-gray-900">
              Request Volume (Last 30 Days)
            </h2>
            <div className="flex items-end gap-1" style={{ height: 160 }}>
              {volume.map((v) => (
                <div
                  key={v.day}
                  className="group relative flex-1"
                  style={{ height: '100%' }}
                >
                  <div
                    className="absolute bottom-0 w-full rounded-t bg-rho-500 transition-all hover:bg-rho-600"
                    style={{
                      height: `${Math.max((v.count / maxVolumeCount) * 100, 2)}%`,
                    }}
                  />
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 hidden group-hover:block whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white shadow-lg">
                    {v.day}: {v.count}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-2 flex justify-between text-xs text-gray-400">
              <span>{volume[0]?.day ?? ''}</span>
              <span>{volume[volume.length - 1]?.day ?? ''}</span>
            </div>
          </section>
        )}

        {/* Human review stats */}
        {reviewStats && (
          <section className="card">
            <h2 className="mb-4 text-base font-semibold text-gray-900">
              Human Review Stats
            </h2>
            <dl className="grid grid-cols-2 gap-4">
              <Stat label="Total Reviews" value={reviewStats.total} />
              <Stat label="Pending" value={reviewStats.pending} />
              <Stat label="Approved" value={reviewStats.approved} />
              <Stat label="Rejected" value={reviewStats.rejected} />
            </dl>
            <div className="mt-4">
              <p className="text-sm text-gray-500">
                Approval Rate:{' '}
                <span className="font-semibold text-gray-900">
                  {reviewStats.approval_rate}%
                </span>
              </p>
            </div>
          </section>
        )}

        {/* Agent performance */}
        {agentPerf.length > 0 && (
          <section className="card">
            <h2 className="mb-4 text-base font-semibold text-gray-900">
              Agent Performance
            </h2>
            <div className="overflow-hidden rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="table-header">Agent</th>
                    <th className="table-header text-right">Runs</th>
                    <th className="table-header text-right">Avg Confidence</th>
                    <th className="table-header text-right">Avg Duration</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {agentPerf.map((a) => (
                    <tr key={a.agent_name}>
                      <td className="table-cell font-medium">{a.agent_name}</td>
                      <td className="table-cell text-right">{a.total_runs}</td>
                      <td className="table-cell text-right">
                        {Math.round(a.avg_confidence * 100)}%
                      </td>
                      <td className="table-cell text-right">
                        {Math.round(a.avg_duration_ms)}ms
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

/* ---------- Helper components ---------- */

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="card flex flex-col items-center">
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
      <p className="mt-1 text-xs text-gray-500">{label}</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="text-lg font-semibold text-gray-900">{value}</dd>
    </div>
  );
}
