import type { JobKind } from './api/types';

export interface FlowMeta {
  key: string;
  label: string;
  shortLabel: string;
  description: string;
  configKey: string;
  icon: string;
}

/** UI flow id (used as button/panel key) → metadata. */
export const FLOWS: FlowMeta[] = [
  {
    key: 'predict',
    label: 'Structure Prediction',
    shortLabel: 'Predict',
    description: 'Predict 3D structure from a FASTA sequence with Boltz-1.',
    configKey: 'boltz',
    icon: 'structure',
  },
  {
    key: 'dock',
    label: 'Molecular Docking',
    shortLabel: 'Dock',
    description: 'Virtual screening of ligands against a protein receptor with AutoDock Vina.',
    configKey: 'docking',
    icon: 'docking',
  },
  {
    key: 'qm',
    label: 'QM Pipeline',
    shortLabel: 'QM',
    description: 'Quantum-mechanical charge refinement with ORCA.',
    configKey: 'orca',
    icon: 'qm',
  },
  {
    key: 'md',
    label: 'Molecular Dynamics',
    shortLabel: 'MD',
    description: 'Full GROMACS simulation (APO or HOLO complex).',
    configKey: 'md',
    icon: 'md',
  },
];

export const FLOW_BY_ID: Record<string, FlowMeta> = Object.fromEntries(
  FLOWS.map((f) => [f.key, f]),
);

/** Backend job kind → UI flow flavor for rendering results. */
export const KIND_TO_FLOW: Record<JobKind, string> = {
  predict: 'predict',
  'predict-boltz': 'predict',
  dock: 'dock',
  simulate: 'md',
  'simulate-holo': 'md',
  'qm-orca': 'qm',
};

export function flowMetaFor(kind: JobKind): FlowMeta {
  return FLOW_BY_ID[KIND_TO_FLOW[kind]] ?? FLOW_BY_ID.predict;
}

export const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  canceled: 'Canceled',
};