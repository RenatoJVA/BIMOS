import type { Job } from '../../api/types';
import { formatDuration, formatTimestamp } from '../../utils/format';
import { bestDockScore, dockHits, jobLabel } from '../../utils/results';
import { StatusBadge } from '../ui/StatusBadge';

interface JobCardProps {
  job: Job;
  onOpen: (job: Job) => void;
}

export function JobCard({ job, onOpen }: JobCardProps) {
  const label = jobLabel(job);
  const dockBest = bestDockScore(job);
  const hasDockHits = dockHits(job).length > 0;

  return (
    <article
      onClick={() => onOpen(job)}
      className="bg-bg-card border border-border rounded-lg p-5 transition-all duration-200 relative shadow-sm hover:border-border-active hover:shadow-md flex flex-col gap-3 cursor-pointer active:translate-y-[1px] focus-visible:outline focus-visible:outline-accent"
      tabIndex={0}
      role="button"
      aria-label={`Open ${job.kind} job ${label}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(job);
        }
      }}
    >
      <div className="flex justify-between items-start gap-3">
        <div className="flex flex-col gap-1.5 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[0.7rem] text-text-secondary uppercase tracking-wider">
              {job.kind.replace(/[-_]/g, ' ')}
            </span>
            {job.meta.max_resources && (
              <span className="text-[0.6rem] font-mono uppercase tracking-wide text-accent border border-accent/40 rounded px-1.5 py-px">
                max
              </span>
            )}
          </div>
          <div className="text-[1.05rem] font-semibold text-text-primary leading-tight truncate" title={label}>
            {label}
          </div>
          <div className="font-mono text-[0.65rem] text-text-secondary opacity-70">
            ID_{job.id.toUpperCase()}
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>

      <div className="flex items-center gap-3 text-[0.72rem] font-mono text-text-secondary">
        <span>created {formatTimestamp(job.created_at)}</span>
        {job.started_at && job.status !== 'pending' && (
          <span>
            · {job.status === 'completed' || job.status === 'failed' || job.status === 'canceled'
              ? `took ${formatDuration(job.created_at, job.finished_at)}`
              : `running ${formatDuration(job.started_at)}`}
          </span>
        )}
      </div>

      {job.error && (
        <div className="text-[0.72rem] font-mono text-danger border-t border-border pt-2" title={job.error}>
          {job.error}
        </div>
      )}

      {hasDockHits && dockBest !== null && (
        <div className="text-[0.72rem] font-mono text-success border-t border-border pt-2">
          best {dockBest.toFixed(2)} kcal/mol
        </div>
      )}
    </article>
  );
}