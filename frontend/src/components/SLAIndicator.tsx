/**
 * Traffic-light SLA indicator.
 *   - Green:  > 24 h remaining (or no deadline)
 *   - Amber:  <= 24 h remaining
 *   - Red:    breached (past deadline)
 */

interface Props {
  deadline: string | null;
  className?: string;
}

export default function SLAIndicator({ deadline, className = '' }: Props) {
  if (!deadline) {
    return (
      <span className={`inline-flex items-center gap-1.5 text-xs text-gray-400 ${className}`}>
        <Circle color="bg-gray-300" />
        N/A
      </span>
    );
  }

  const now = Date.now();
  const dl = new Date(deadline).getTime();
  const hoursLeft = (dl - now) / (1000 * 60 * 60);

  let color: string;
  let label: string;

  if (hoursLeft < 0) {
    color = 'bg-sla-red';
    label = 'Breached';
  } else if (hoursLeft <= 24) {
    color = 'bg-sla-amber';
    label = `${Math.round(hoursLeft)}h left`;
  } else {
    color = 'bg-sla-green';
    const days = Math.floor(hoursLeft / 24);
    label = `${days}d left`;
  }

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${className}`}>
      <Circle color={color} />
      {label}
    </span>
  );
}

function Circle({ color }: { color: string }) {
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />;
}
