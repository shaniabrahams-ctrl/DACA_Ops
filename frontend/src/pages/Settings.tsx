import { useEffect, useState } from 'react';
import { oversight as oversightApi } from '../api/client';
import type { OversightConfig } from '../types';
import { DACA_STATUSES, ALWAYS_HUMAN_STAGES } from '../types';

export default function Settings() {
  const [configs, setConfigs] = useState<OversightConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Editable local state for system config
  const [systemMode, setSystemMode] = useState<'FULL_AUTOMATION' | 'HUMAN_OVERSIGHT'>(
    'HUMAN_OVERSIGHT',
  );
  const [systemThreshold, setSystemThreshold] = useState(0.85);

  const fetchConfigs = () => {
    setLoading(true);
    setError(null);
    oversightApi
      .getAll()
      .then((data) => {
        setConfigs(data);
        const sys = data.find((c) => c.scope === 'SYSTEM');
        if (sys) {
          setSystemMode(sys.mode);
          setSystemThreshold(sys.confidence_threshold);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleSaveSystem = async () => {
    setSaving(true);
    try {
      await oversightApi.updateSystem(systemMode, systemThreshold);
      fetchConfigs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleStageToggle = async (stage: string, currentMode: string) => {
    if (ALWAYS_HUMAN_STAGES.has(stage)) return;
    const newMode =
      currentMode === 'FULL_AUTOMATION' ? 'HUMAN_OVERSIGHT' : 'FULL_AUTOMATION';
    setSaving(true);
    try {
      await oversightApi.updateStage(stage, newMode, systemThreshold);
      fetchConfigs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  // Build a map of stage -> config for easy lookup
  const stageConfigMap = new Map<string, OversightConfig>();
  configs.forEach((c) => {
    if (c.scope === 'STAGE' && c.stage) stageConfigMap.set(c.stage, c);
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Settings</h1>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="py-20 text-center text-gray-400">Loading settings...</div>
      ) : (
        <div className="space-y-8">
          {/* System-wide oversight toggle */}
          <section className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              System-Wide Oversight Mode
            </h2>
            <div className="flex items-center gap-6">
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="system-mode"
                    checked={systemMode === 'HUMAN_OVERSIGHT'}
                    onChange={() => setSystemMode('HUMAN_OVERSIGHT')}
                    className="h-4 w-4 text-rho-600 focus:ring-rho-500"
                  />
                  <span className="text-sm font-medium text-gray-700">
                    Human Oversight
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="system-mode"
                    checked={systemMode === 'FULL_AUTOMATION'}
                    onChange={() => setSystemMode('FULL_AUTOMATION')}
                    className="h-4 w-4 text-rho-600 focus:ring-rho-500"
                  />
                  <span className="text-sm font-medium text-gray-700">
                    Full Automation
                  </span>
                </label>
              </div>
              <button
                onClick={handleSaveSystem}
                disabled={saving}
                className="btn-primary"
              >
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
            <p className="mt-3 text-xs text-gray-500">
              When set to Human Oversight, all agent-driven transitions will pause for
              human approval unless the stage is explicitly set to Full Automation below.
            </p>
          </section>

          {/* Confidence threshold slider */}
          <section className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Confidence Threshold
            </h2>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(systemThreshold * 100)}
                onChange={(e) => setSystemThreshold(Number(e.target.value) / 100)}
                className="h-2 flex-1 cursor-pointer appearance-none rounded-lg bg-gray-200 accent-rho-600"
              />
              <span className="w-16 text-right text-sm font-medium text-gray-700">
                {Math.round(systemThreshold * 100)}%
              </span>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              Agent recommendations below this confidence level will automatically be
              routed for human review regardless of the oversight mode.
            </p>
          </section>

          {/* Per-stage overrides grid */}
          <section className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Per-Stage Overrides
            </h2>
            <p className="mb-4 text-xs text-gray-500">
              Stages marked with a lock icon always require human approval and cannot be
              automated.
            </p>

            <div className="overflow-hidden rounded-lg border border-gray-200">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="table-header">Stage</th>
                    <th className="table-header text-center">Mode</th>
                    <th className="table-header text-center">Confidence Threshold</th>
                    <th className="table-header text-center">Always Human</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {DACA_STATUSES.map((stage) => {
                    const isLocked = ALWAYS_HUMAN_STAGES.has(stage);
                    const stageConfig = stageConfigMap.get(stage);
                    const mode = stageConfig?.mode ?? systemMode;
                    const threshold = stageConfig?.confidence_threshold ?? systemThreshold;

                    return (
                      <tr key={stage} className={isLocked ? 'bg-gray-50' : ''}>
                        <td className="table-cell font-medium">
                          {stage}
                        </td>
                        <td className="table-cell text-center">
                          {isLocked ? (
                            <span className="text-xs text-gray-400">HUMAN_OVERSIGHT</span>
                          ) : (
                            <button
                              onClick={() => handleStageToggle(stage, mode)}
                              disabled={saving}
                              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                                mode === 'FULL_AUTOMATION'
                                  ? 'bg-green-100 text-green-800 hover:bg-green-200'
                                  : 'bg-amber-100 text-amber-800 hover:bg-amber-200'
                              }`}
                            >
                              {mode === 'FULL_AUTOMATION' ? 'Auto' : 'Human'}
                            </button>
                          )}
                        </td>
                        <td className="table-cell text-center text-sm text-gray-600">
                          {Math.round(threshold * 100)}%
                        </td>
                        <td className="table-cell text-center">
                          {isLocked ? (
                            <LockIcon />
                          ) : (
                            <span className="text-gray-300">&mdash;</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* Notification channels placeholder */}
          <section className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Notification Channels
            </h2>
            <p className="text-sm text-gray-500">
              Configure Slack, email, and webhook notification channels for pipeline
              events. Integration settings are managed via environment variables.
            </p>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-md border border-gray-200 p-4">
                <h3 className="text-sm font-medium text-gray-900">Slack</h3>
                <p className="mt-1 text-xs text-gray-500">
                  Configured via SLACK_WEBHOOK_URL
                </p>
              </div>
              <div className="rounded-md border border-gray-200 p-4">
                <h3 className="text-sm font-medium text-gray-900">Email</h3>
                <p className="mt-1 text-xs text-gray-500">
                  Configured via GMAIL_CREDENTIALS
                </p>
              </div>
              <div className="rounded-md border border-gray-200 p-4">
                <h3 className="text-sm font-medium text-gray-900">Webhooks</h3>
                <p className="mt-1 text-xs text-gray-500">
                  Configured via WEBHOOK_URLS
                </p>
              </div>
            </div>
          </section>

          {/* Auth config placeholder */}
          <section className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Authentication
            </h2>
            <p className="text-sm text-gray-500">
              Authentication is handled via the X-Actor-Id header (MVP).
              OAuth/SSO integration planned for a future sprint.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}

function LockIcon() {
  return (
    <svg
      className="mx-auto h-5 w-5 text-amber-500"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"
      />
    </svg>
  );
}
