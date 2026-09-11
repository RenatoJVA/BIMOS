import type {
  ConfigProfilesResponse,
  Job,
  LogsResponse,
  SystemStats,
} from './types';
import { recordStats } from '../utils/history';

export const API_BASE = 'http://localhost:8000/api/v1';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
      else if (body?.detail) detail = `${typeof body.detail}`;
    } catch {
      /* keep statusText */
    }
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function fetchJobs(signal?: AbortSignal): Promise<Job[]> {
  return request<Job[]>('/jobs', { signal });
}

export function fetchJob(jobId: string, signal?: AbortSignal): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`, { signal });
}

export function fetchLogs(jobId: string, tail = 500): Promise<LogsResponse> {
  return request<LogsResponse>(`/jobs/${jobId}/logs?tail=${tail}`);
}

export function cancelJob(jobId: string): Promise<{ status: string; job_id: string }> {
  return request(`/jobs/${jobId}/cancel`, { method: 'POST' });
}

export function deleteJob(jobId: string): Promise<void> {
  return request<void>(`/jobs/${jobId}`, { method: 'DELETE' });
}

export async function fetchSystemStats(signal?: AbortSignal): Promise<SystemStats> {
  const stats = await request<SystemStats>('/system/stats', { signal });
  recordStats({
    cpu: stats.cpu,
    memory: stats.memory,
    gpuUtil: stats.gpu?.utilization ?? 0,
    vramPct: stats.gpu?.memory_percent ?? 0,
  });
  return stats;
}

export function fetchConfigProfiles(signal?: AbortSignal): Promise<ConfigProfilesResponse> {
  return request<ConfigProfilesResponse>('/config/profiles', { signal });
}

interface JsonParams {
  fasta_content: string;
  name: string;
  num_models?: number;
  max_resources: boolean;
}

export function launchPrediction(params: JsonParams): Promise<Job> {
  return request<Job>('/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
}

interface FileParams {
  max_resources: boolean;
  [k: string]: unknown;
}

function fileBody(fields: Record<string, File | string | number | boolean>): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null) continue;
    form.append(key, value instanceof File ? value : String(value));
  }
  return form;
}

export function launchDock(files: { protein: File; ligands: File }, params: Omit<FileParams, 'max_resources'> & FileParams): Promise<Job> {
  const form = fileBody({
    protein: files.protein,
    ligands: files.ligands,
    ...params,
  });
  return request<Job>('/dock', { method: 'POST', body: form });
}

export function launchSimulate(files: { protein: File }, params: FileParams): Promise<Job> {
  const form = fileBody({ protein: files.protein, ...params });
  return request<Job>('/simulate', { method: 'POST', body: form });
}

export function launchSimulateHolo(
  files: { protein: File; ligand_gro: File; ligand_itp: File },
  params: FileParams,
): Promise<Job> {
  const form = fileBody({ ...files, ...params });
  return request<Job>('/simulate-holo', { method: 'POST', body: form });
}

export function launchQmOrca(files: { gro: File; itp: File }, params: { charge: number } & FileParams): Promise<Job> {
  const form = fileBody({ gro: files.gro, itp: files.itp, ...params });
  return request<Job>('/qm-orca-files', { method: 'POST', body: form });
}

export function jobLogStreamUrl(jobId: string): string {
  return `${API_BASE}/jobs/${jobId}/logs/stream`;
}