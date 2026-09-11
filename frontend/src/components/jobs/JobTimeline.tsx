import type { Job } from '../../api/types';
import { formatTimestamp } from '../../utils/format';

function Step({
  label,
  time,
  done,
}: {
  label: string;
  time?: string | null;
  done: boolean;
}) {
  return (
    <li className="flex items-start gap-3">
      <span
        className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${
          done ? 'bg-accent' : 'bg-border'
        }`}
        aria-hidden="true"
      />
      <div className="flex flex-col">
        <span className={`text-[0.8rem] font-mono ${done ? 'text-text-primary' : 'text-text-secondary'}`}>
          {label}
        </span>
        {time ? (
          <span className="text-[0.72rem] font-mono text-text-secondary opacity-70">
            {formatTimestamp(time)}
          </span>
        ) : (
          <span className="text-[0.72rem] font-mono text-text-secondary opacity-50">waiting</span>
        )}
      </div>
    </li>
  );
}

export function JobTimeline({ job }: { job: Job }) {
  return (
    <ul className="flex flex-col gap-2">
      <Step label="Created" time={job.created_at} done />
      <Step label="Started" time={job.started_at} done={Boolean(job.started_at)} />
      <Step
        label={
          job.status === 'failed'
            ? 'Failed'
            : job.status === 'canceled'
              ? 'Canceled'
              : job.status === 'completed'
                ? 'Completed'
                : 'Running'
        }
        time={job.finished_at}
        done={job.status === 'completed' || job.status === 'failed' || job.status === 'canceled'}
      />
    </ul>
  );
}