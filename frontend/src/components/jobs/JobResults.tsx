import type { Job } from '../../api/types';
import { baseName, dockHits, predictConfidence, predictStructFile } from '../../utils/results';
import { CopyButton } from '../ui/CopyButton';
import { PanelLabel } from '../ui/primitives';

export function JobResults({ job }: { job: Job }) {
  if (job.status !== 'completed' || !job.results) return null;

  if (job.kind === 'dock') return <DockResults job={job} />;
  if (job.kind === 'predict' || job.kind === 'predict-boltz') return <PredictResults job={job} />;
  return <MiscResults job={job} />;
}

function PredictResults({ job }: { job: Job }) {
  const conf = predictConfidence(job);
  const struct = predictStructFile(job);
  return (
    <section className="flex flex-col gap-2">
      <PanelLabel>Prediction</PanelLabel>
      <div className="flex items-center gap-3">
        <span className="text-[0.75rem] font-mono text-text-secondary">Confidence</span>
        <span className="text-lg font-bold text-text-primary font-mono">
          {conf !== undefined ? conf.toFixed(3) : '—'}
        </span>
      </div>
      {struct && (
        <div className="flex items-center justify-between gap-2 border border-border rounded-md px-3 py-2">
          <span className="text-[0.75rem] font-mono text-text-primary truncate" title={struct}>
            {baseName(struct)}
          </span>
          <CopyButton value={struct} label="Copy path" />
        </div>
      )}
      <JobOutputDir job={job} />
    </section>
  );
}

function DockResults({ job }: { job: Job }) {
  const hits = dockHits(job).sort((a, b) => a.best_score_kcal_mol - b.best_score_kcal_mol);
  if (hits.length === 0) {
    return (
      <section className="flex flex-col gap-2">
        <PanelLabel>Docking</PanelLabel>
        <p className="text-[0.8rem] font-mono text-text-secondary">Completed with no scored hits.</p>
        <JobOutputDir job={job} />
      </section>
    );
  }
  return (
    <section className="flex flex-col gap-2">
      <PanelLabel>Top docking hits</PanelLabel>
      <ol className="flex flex-col gap-1.5">
        {hits.slice(0, 8).map((hit, i) => (
          <li key={hit.complex} className="flex items-center justify-between gap-3 border border-border rounded-md px-3 py-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className={`text-[0.7rem] font-mono ${i === 0 ? 'text-accent' : 'text-text-secondary'}`}>
                {i + 1}
              </span>
              <span className="text-[0.78rem] font-mono truncate">{baseName(hit.complex)}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={`text-[0.8rem] font-mono ${i === 0 ? 'text-success font-bold' : 'text-text-primary'}`}>
                {hit.best_score_kcal_mol.toFixed(2)} kcal/mol
              </span>
              <CopyButton value={hit.best_pose} label="pose" />
            </div>
          </li>
        ))}
      </ol>
      {hits.length > 8 && (
        <p className="text-[0.7rem] font-mono text-text-secondary opacity-70">
          + {hits.length - 8} more hits in the output directory
        </p>
      )}
      <JobOutputDir job={job} />
    </section>
  );
}

function MiscResults({ job }: { job: Job }) {
  return (
    <section className="flex flex-col gap-2">
      <PanelLabel>{job.kind.replace(/[-_]/g, ' ')}</PanelLabel>
      <p className="text-[0.8rem] font-mono text-success">Completed successfully.</p>
      <JobOutputDir job={job} />
    </section>
  );
}

function JobOutputDir({ job }: { job: Job }) {
  if (!job.output_dir) return null;
  return (
    <div className="flex items-center justify-between gap-2 border border-border rounded-md px-3 py-2 mt-1">
      <span className="text-[0.75rem] font-mono text-text-secondary truncate" title={job.output_dir}>
        {job.output_dir}
      </span>
      <CopyButton value={job.output_dir} label="Copy output path" />
    </div>
  );
}