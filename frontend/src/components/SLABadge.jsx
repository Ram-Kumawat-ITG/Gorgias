// SLA status badge — green/yellow/red with hover tooltip showing due date
import clsx from 'clsx';

const SLA_COLORS = {
  ok: 'bg-green-100 text-green-700',
  warning: 'bg-yellow-100 text-yellow-700',
  breached: 'bg-red-100 text-red-700',
};

export default function SLABadge({ slaStatus, slaDueAt }) {
  if (!slaStatus || slaStatus === 'ok') return null;

  const dueStr = slaDueAt ? new Date(slaDueAt).toLocaleString() : 'N/A';

  return (
    <span
      className={clsx('badge', SLA_COLORS[slaStatus] || SLA_COLORS.ok)}
      title={`SLA due: ${dueStr}`}
    >
      SLA: {slaStatus}
    </span>
  );
}
