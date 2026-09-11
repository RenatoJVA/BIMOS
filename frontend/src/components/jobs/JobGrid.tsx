import { useMemo, useState } from 'react';
import type { Job, JobKind, JobStatus } from '../../api/types';
import { STATUS_LABEL } from '../../config';
import { Select } from '../ui/Select';
import { Skeleton } from '../ui/primitives';
import { EmptyState } from '../ui/EmptyState';
import { JobCard } from './JobCard';
import { jobLabel } from '../../utils/results';

const KIND_FILTERS: { label: string; value: JobKind | 'all'; match: (k: JobKind) => boolean }[] = [
  { label: 'All', value: 'all', match: () => true },
  {
    label: 'Prediction',
    value: 'predict',
    match: (k) => k === 'predict' || k === 'predict-boltz',
  },
  { label: 'Docking', value: 'dock', match: (k) => k === 'dock' },
  { label: 'MD', value: 'simulate', match: (k) => k === 'simulate' || k === 'simulate-holo' },
  { label: 'QM', value: 'qm-orca', match: (k) => k === 'qm-orca' },
];

const STATUS_FILTERS: { label: string; value: JobStatus | 'all' }[] = [
  { label: 'All statuses', value: 'all' },
  { label: 'Pending', value: 'pending' },
  { label: 'Running', value: 'running' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
  { label: 'Canceled', value: 'canceled' },
];

function searchableText(job: Job): string {
  return [
    job.id,
    job.kind,
    jobLabel(job),
    job.meta.name,
    typeof job.meta.fasta === 'string' ? job.meta.fasta : '',
    typeof job.meta.protein === 'string' ? job.meta.protein : '',
    typeof job.meta.gro === 'string' ? job.meta.gro : '',
    STATUS_LABEL[job.status] ?? job.status,
  ]
    .filter((x): x is string => typeof x === 'string')
    .join(' ')
    .toLowerCase();
}

interface JobGridProps {
  jobs: Job[];
  loading: boolean;
  onOpen: (job: Job) => void;
}

export function JobGrid({ jobs, loading, onOpen }: JobGridProps) {
  const [kindFilter, setKindFilter] = useState<JobKind | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'all'>('all');
  const [query, setQuery] = useState('');

  const kindSelector = KIND_FILTERS.find((f) => f.value === kindFilter) ?? KIND_FILTERS[0];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter(
      (j) =>
        kindSelector.match(j.kind) &&
        (statusFilter === 'all' || j.status === statusFilter) &&
        (!q || searchableText(j).includes(q)),
    );
  }, [jobs, kindSelector, statusFilter, query]);

  const filtersActive = kindFilter !== 'all' || statusFilter !== 'all' || query.trim() !== '';

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-border overflow-hidden bg-bg-card" role="group" aria-label="Filter by pipeline">
          {KIND_FILTERS.map((f) => (
            <FilterSegment
              key={f.value}
              label={f.label}
              active={kindFilter === f.value}
              onClick={() => setKindFilter(f.value)}
            />
          ))}
        </div>

        <Select<JobStatus | 'all'>
          value={statusFilter}
          options={STATUS_FILTERS}
          onChange={setStatusFilter}
          label="Filter by status"
        />

        <div className="relative min-w-[180px] flex-1 max-w-[260px]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary text-[0.8rem]" aria-hidden="true">
            ⌕
          </span>
          <input
            type="search"
            placeholder="Search jobs…"
            aria-label="Search jobs by id, name, pipeline or status"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-bg-card border border-border text-text-primary pl-8 pr-3 py-2 font-mono text-[0.8rem] rounded-md focus:outline-none focus:border-accent focus-visible:outline-2 focus-visible:outline-accent transition-all"
          />
        </div>

        {filtersActive && (
          <button
            onClick={() => {
              setKindFilter('all');
              setStatusFilter('all');
              setQuery('');
            }}
            className="text-[0.72rem] font-mono uppercase tracking-wider text-text-secondary hover:text-text-primary cursor-pointer transition-colors"
          >
            Clear ×
          </button>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-bg-card border border-border rounded-lg p-5 flex flex-col gap-3">
              <Skeleton className="w-24 h-4" />
              <Skeleton className="w-3/4 h-5" />
              <Skeleton className="w-1/2 h-3" />
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        jobs.length === 0 ? (
          <EmptyState
            title="No jobs yet"
            hint={
              <span>
                Launch your first pipeline above, or press <strong>Enter</strong> on a selected pipeline to get started.
              </span>
            }
            icon="⚗️"
          />
        ) : (
          <EmptyState title="No jobs match the current filters" hint="Try clearing filters or the search box." />
        )
      ) : (
        <>
          <div className="text-[0.7rem] font-mono text-text-secondary uppercase tracking-wider">
            {filtered.length} {filtered.length === 1 ? 'job' : 'jobs'}
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
            {filtered.map((job) => (
              <JobCard key={job.id} job={job} onOpen={onOpen} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function FilterSegment({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`px-3.5 py-2 text-[0.8rem] transition-colors cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
        active
          ? 'bg-accent text-bg-page font-semibold'
          : 'text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
      } border-r border-border last:border-r-0`}
    >
      {label}
    </button>
  );
}