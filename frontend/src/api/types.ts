export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'canceled';

export type JobKind = 'predict' | 'predict-boltz' | 'dock' | 'simulate' | 'simulate-holo' | 'qm-orca';

export interface DockingHit {
  complex: string;
  best_pose: string;
  best_score_kcal_mol: number;
}

export interface JobMeta {
  [k: string]: unknown;
  name?: string;
  max_resources?: boolean;
}

export interface Job {
  id: string;
  kind: JobKind;
  status: JobStatus;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
  output_dir?: string | null;
  meta: JobMeta;
  results?: unknown;
}

export interface PredictResults {
  status?: string;
  struct_file?: string;
  confidence?: number;
  output_dir?: string;
}

export interface DockResults {
  status?: string;
  results?: DockingHit[];
  output_dir?: string;
}

export interface QmResults {
  status?: string;
  results?: string[];
  output_dir?: string;
}

export interface MdResults {
  status?: string;
  output_dir?: string;
}

export type JobResults = PredictResults | DockResults | QmResults | MdResults | null;

export interface SystemStats {
  cpu: number;
  memory: number;
  gpu: {
    utilization: number;
    memory_used: number;
    memory_total: number;
    memory_percent: number;
  } | null;
}

export interface ProcessConfigInfo {
  profile: 'default' | 'custom' | 'max';
  custom: boolean;
  path: string;
}

export interface ConfigProfilesResponse {
  config_dir: string;
  processes: Record<string, ProcessConfigInfo>;
}

export interface LogsResponse {
  job_id: string;
  logs: string[];
}