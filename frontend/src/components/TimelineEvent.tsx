import type { AuditLog } from '../types';

interface Props {
  event: AuditLog;
}

/** Single audit-log entry rendered for a timeline view. */
export default function TimelineEvent({ event }: Props) {
  const time = new Date(event.created_at);

  return (
    <div className="relative flex gap-4 pb-6">
      {/* Vertical line */}
      <div className="flex flex-col items-center">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-rho-200 bg-white">
          <ActorIcon type={event.actor_type} />
        </div>
        <div className="w-px flex-1 bg-gray-200" />
      </div>

      {/* Content */}
      <div className="flex-1 pt-0.5">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-gray-900">{event.action}</span>
          <span className="text-xs text-gray-400">
            {time.toLocaleDateString()} {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

        <p className="mt-0.5 text-xs text-gray-500">
          by {event.actor_type === 'AGENT' ? 'Agent' : 'User'}: {event.actor_id}
        </p>

        {event.rationale && (
          <p className="mt-1 text-sm text-gray-600 italic">"{event.rationale}"</p>
        )}

        {/* State diff */}
        {(event.before_state || event.after_state) && (
          <div className="mt-2 flex gap-4 text-xs">
            {event.before_state && (
              <div className="rounded bg-red-50 px-2 py-1 text-red-700">
                <span className="font-medium">Before:</span>{' '}
                {JSON.stringify(event.before_state)}
              </div>
            )}
            {event.after_state && (
              <div className="rounded bg-green-50 px-2 py-1 text-green-700">
                <span className="font-medium">After:</span>{' '}
                {JSON.stringify(event.after_state)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ActorIcon({ type }: { type: string }) {
  if (type === 'AGENT') {
    return (
      <svg className="h-4 w-4 text-rho-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 14.5M14.25 3.104c.251.023.501.05.75.082M19.8 14.5l-2.047 2.232a2.25 2.25 0 01-1.624.698H7.872a2.25 2.25 0 01-1.624-.698L4.2 14.5" />
      </svg>
    );
  }
  return (
    <svg className="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
    </svg>
  );
}
