import type { DockingHit, Job, ScreenHit } from '../api/types';

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

export function screenHits(job: Job): ScreenHit[] {
  const r = readResults<{
    candidates?: unknown;
    vina_scores?: unknown;
    holo_dirs?: unknown;
    hirsh_itps?: unknown;
  }>(job);
  if (!r || !Array.isArray(r.candidates)) return [];
  return r.candidates
    .filter((candidate): candidate is string => typeof candidate === 'string')
    .map((candidate, i) => ({
      candidate,
      vina_score_kcal_mol:
        Array.isArray(r.vina_scores) && typeof r.vina_scores[i] === 'number'
          ? r.vina_scores[i]
          : undefined,
      holo_dir:
        Array.isArray(r.holo_dirs) && typeof r.holo_dirs[i] === 'string'
          ? r.holo_dirs[i]
          : undefined,
      hirsh_itp:
        Array.isArray(r.hirsh_itps) && typeof r.hirsh_itps[i] === 'string'
          ? r.hirsh_itps[i]
          : undefined,
    }));
}

export function screenReport(job: Job): string | undefined {
  return readResults<{ report?: string }>(job)?.report;
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
    .replace('qm-g16', 'qm gaussian')
    .replace('workflow-holo-batch', 'md (holo batch)')
    .replace('workflow-holo', 'md (holo)')
    .replace('workflow-apo', 'md (apo)')
    .replace(/[-_]/g, ' ');
}