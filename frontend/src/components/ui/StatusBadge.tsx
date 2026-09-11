import type { JobStatus } from '../../api/types';
import { STATUS_LABEL } from '../../config';

const STATUS_STYLE: Record<JobStatus, string> = {
  pending:
    'text-warning bg-transparent border-warning',
  running:
    'text-accent bg-accent-glow border-accent',
  completed:
    'text-success bg-transparent border-success',
  failed:
    'text-danger bg-transparent border-danger',
  canceled:
    'text-text-secondary bg-transparent border-border',
};

export function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-2 px-3 py-1 rounded-[4px] text-[0.75rem] font-mono font-medium border ${STATUS_STYLE[status]}`}
    >
      {status === 'running' && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" aria-hidden="true" />
      )}
      <span className="capitalize">{STATUS_LABEL[status] ?? status}</span>
    </span>
  );
}