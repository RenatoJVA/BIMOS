import type { DockingHit, Job } from '../api/types';

function readResults<T>(job: Job): T | null {
  if (!job.results) return null;
  if (typeof job.results !== 'object') return null;
  return job.results as T;
}

export function dockHits(job: Job): DockingHit[] {
  const r = readResults<{ results?: unknown }>(job);
  if (!r || !Array.isArray(r.results)) return [];
  return r.results.filter(
    (x): x is DockingHit => typeof x === 'object' && x !== null && 'complex' in x,
  );
}

export function bestDockScore(job: Job): number | null {
  const hits = dockHits(job);
  if (hits.length === 0) return null;
  return Math.min(...hits.map((h) => h.best_score_kcal_mol));
}

export function predictConfidence(job: Job): number | undefined {
  return readResults<{ confidence?: number }>(job)?.confidence;
}

export function predictStructFile(job: Job): string | undefined {
  return readResults<{ struct_file?: string }>(job)?.struct_file;
}

export function jobLabel(job: Job): string {
  const meta = job.meta ?? {};
  if (typeof meta.name === 'string' && meta.name) return meta.name;
  if (typeof meta.fasta === 'string') return meta.fasta.split('/').pop() ?? '';
  if (typeof meta.protein === 'string') {
    const base = meta.protein.split('/').pop() ?? '';
    return base.replace(/\.pdb$/i, '');
  }
  if (typeof meta.gro === 'string') return meta.gro.split('/').pop() ?? '';
  return job.id;
}

export function baseName(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}

export function kindDisplay(kind: string): string {
  return kind
    .replace('predict-boltz', 'boltz prediction')
    .replace('simulate-holo', 'md (holo)')
    .replace('simulate', 'md (apo)')
    .replace('qm-orca', 'qm orca')
    .replace(/[-_]/g, ' ');
}