import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { launchDock, launchPrediction, launchQmOrca, launchSimulate, launchSimulateHolo } from '../../api/client';
import { FLOW_BY_ID } from '../../config';
import { Button } from '../ui/Button';
import { Field, inputClass } from '../ui/Field';
import { FileDrop } from './FileDrop';
import { ConfigBar } from './ConfigBar';

export type FlowId = 'predict' | 'dock' | 'qm' | 'md';

interface FlowLauncherProps {
  activeFlow: FlowId | null;
  onActiveFlowChange: (flow: FlowId | null) => void;
  maxResources: boolean;
  onMaxResourcesChange: (value: boolean) => void;
  onJobStarted: () => void;
  notify: (type: 'success' | 'error' | 'info', message: string) => void;
}

export function FlowLauncher({
  activeFlow,
  onActiveFlowChange,
  maxResources,
  onMaxResourcesChange,
  onJobStarted,
  notify,
}: FlowLauncherProps) {
  return (
    <div className="mb-10 animate-fadeIn">
      <ConfigBar
        activeFlow={activeFlow}
        maxResources={maxResources}
        onMaxResourcesChange={onMaxResourcesChange}
      />

      <div className="flex flex-wrap gap-3 mb-6" role="tablist" aria-label="Pipeline">
        {(Object.keys(FLOW_BY_ID) as FlowId[]).map((id) => {
          const meta = FLOW_BY_ID[id];
          const active = activeFlow === id;
          return (
            <button
              key={id}
              role="tab"
              aria-selected={active}
              onClick={() => {
                if (active) onActiveFlowChange(null);
                else onActiveFlowChange(id);
              }}
              className={`px-5 py-2.5 rounded-lg border font-medium text-[0.85rem] transition-all duration-200 cursor-pointer focus-visible:outline focus-visible:outline-accent ${
                active
                  ? 'bg-accent text-bg-page border-accent font-semibold'
                  : 'bg-bg-card border-border text-text-secondary hover:border-border-active hover:text-text-primary'
              }`}
            >
              {meta.shortLabel}
            </button>
          );
        })}
      </div>

      {activeFlow === 'predict' && (
        <PredictForm
          maxResources={maxResources}
          onDone={onJobStarted}
          notify={notify}
        />
      )}
      {activeFlow === 'dock' && (
        <DockForm maxResources={maxResources} onDone={onJobStarted} notify={notify} />
      )}
      {activeFlow === 'qm' && (
        <QmForm maxResources={maxResources} onDone={onJobStarted} notify={notify} />
      )}
      {activeFlow === 'md' && (
        <MdForm maxResources={maxResources} onDone={onJobStarted} notify={notify} />
      )}
    </div>
  );
}

/* ── Form shell ──────────────────────────────────────────────────────────── */
function Panel({
  title,
  description,
  onSubmit,
  submitting,
  submitDisabled,
  children,
}: {
  title: string;
  description: string;
  onSubmit: (e: FormEvent) => void;
  submitting: boolean;
  submitDisabled?: boolean;
  children: ReactNode;
}) {
  return (
    <form
      onSubmit={onSubmit}
      className="bg-bg-card border border-border rounded-lg p-6 flex flex-col gap-5 shadow-sm animate-fadeIn"
    >
      <div className="flex flex-col gap-1">
        <h3 className="text-lg font-bold text-text-primary">{title}</h3>
        <p className="text-[0.8rem] text-text-secondary">{description}</p>
      </div>
      {children}
      <Button type="submit" loading={submitting} disabled={submitDisabled} className="self-start">
        {submitting ? 'Launching…' : 'Launch job'}
      </Button>
    </form>
  );
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="text-[0.8rem] font-mono text-danger border border-danger/40 rounded-md px-3 py-2">
      {message}
    </p>
  );
}

/* ── Predict ─────────────────────────────────────────────────────────────── */
function PredictForm({
  maxResources,
  onDone,
  notify,
}: {
  maxResources: boolean;
  onDone: () => void;
  notify: (t: 'success' | 'error' | 'info', m: string) => void;
}) {
  const [name, setName] = useState('');
  const [fasta, setFasta] = useState('');
  const [numModels, setNumModels] = useState(5);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = fasta.trim();
    if (!trimmed.startsWith('>') && !trimmed.includes('\n')) {
      setError('Provide the sequence as FASTA (a name line starting with “>”, then the sequence).');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const job = await launchPrediction({
        fasta_content: trimmed,
        name: name.trim() || 'protein_job',
        num_models: numModels,
        max_resources: maxResources,
      });
      notify('success', `Prediction started (${job.id}) — Boltz-1 will run on GPU.`);
      onDone();
    } catch (err) {
      notify('error', `Prediction failed: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      title="Boltz-1 Structure Prediction"
      description="Predict a 3D structure from a FASTA sequence. Runs on the GPU."
      onSubmit={submit}
      submitting={submitting}
    >
      <Input name="Predict name" value={name} onChange={setName} placeholder="protein_job (optional)" />
      <Field label="FASTA sequence" htmlFor="predict-fasta" hint="Best when pasted raw from a FASTA file.">
        <textarea
          id="predict-fasta"
          value={fasta}
          onChange={(e) => setFasta(e.target.value)}
          required
          placeholder={'>my_protein\nMEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDE…'}
          className={`${inputClass} min-h-[140px] resize-y`}
        />
      </Field>
      <Field label="Number of models" htmlFor="predict-models" hint="More models = more sampling; fewer = faster.">
        <input
          id="predict-models"
          type="number"
          min={1}
          max={20}
          value={numModels}
          onChange={(e) => setNumModels(Math.max(1, Number(e.target.value) || 1))}
          className={`${inputClass} w-32`}
        />
      </Field>
      {error && <FormError message={error} />}
    </Panel>
  );
}

function Input({
  name,
  value,
  onChange,
  placeholder,
}: {
  name: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  const id = `field-${name.toLowerCase().replace(/\s+/g, '-')}`;
  return (
    <Field label={name} htmlFor={id}>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={inputClass}
      />
    </Field>
  );
}

/* ── Dock ────────────────────────────────────────────────────────────────── */
function DockForm({
  maxResources,
  onDone,
  notify,
}: {
  maxResources: boolean;
  onDone: () => void;
  notify: (t: 'success' | 'error' | 'info', m: string) => void;
}) {
  const [protein, setProtein] = useState<File | null>(null);
  const [ligands, setLigands] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!protein || !ligands) {
      setError('Both a protein (PDB) and a ligands (SDF) file are required.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const job = await launchDock({ protein, ligands }, { max_resources: maxResources });
      notify('success', `Docking started (${job.id}).`);
      onDone();
    } catch (err) {
      notify('error', `Docking failed: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      title="Molecular Docking (AutoDock Vina)"
      description="Screen an SDF set of ligands against a PDB receptor."
      onSubmit={submit}
      submitting={submitting}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FileDrop id="dock-protein" label="Protein (PDB)" accept=".pdb" file={protein} onFileSelect={setProtein} />
        <FileDrop id="dock-ligands" label="Ligands (SDF)" accept=".sdf" file={ligands} onFileSelect={setLigands} />
      </div>
      {error && <FormError message={error} />}
    </Panel>
  );
}

/* ── QM ──────────────────────────────────────────────────────────────────── */
function QmForm({
  maxResources,
  onDone,
  notify,
}: {
  maxResources: boolean;
  onDone: () => void;
  notify: (t: 'success' | 'error' | 'info', m: string) => void;
}) {
  const [gro, setGro] = useState<File | null>(null);
  const [itp, setItp] = useState<File | null>(null);
  const [charge, setCharge] = useState('0');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!gro || !itp) {
      setError('Both a coordinates (GRO) and a topology (ITP) file are required.');
      return;
    }
    const parsed = Number(charge);
    if (!Number.isInteger(parsed)) {
      setError('Total charge must be an integer.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const job = await launchQmOrca(
        { gro, itp },
        { charge: parsed, max_resources: maxResources },
      );
      notify('success', `QM pipeline started (${job.id}).`);
      onDone();
    } catch (err) {
      notify('error', `QM failed: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      title="ORCA QM Pipeline"
      description="Refine atomic charges with an ORCA quantum-mechanical calculation."
      onSubmit={submit}
      submitting={submitting}
      submitDisabled={!gro || !itp}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <FileDrop id="qm-gro" label="Structure (GRO)" accept=".gro" file={gro} onFileSelect={setGro} />
        <FileDrop id="qm-itp" label="Topology (ITP)" accept=".itp" file={itp} onFileSelect={setItp} />
      </div>
      <Field label="Total charge" htmlFor="qm-charge" hint="Net molecular charge of the system.">
        <input
          id="qm-charge"
          type="number"
          step={1}
          value={charge}
          onChange={(e) => setCharge(e.target.value)}
          className={`${inputClass} w-32`}
        />
      </Field>
      {error && <FormError message={error} />}
    </Panel>
  );
}

/* ── MD ──────────────────────────────────────────────────────────────────── */
type MdMode = 'apo' | 'holo';

function MdForm({
  maxResources,
  onDone,
  notify,
}: {
  maxResources: boolean;
  onDone: () => void;
  notify: (t: 'success' | 'error' | 'info', m: string) => void;
}) {
  const [mode, setMode] = useState<MdMode>('apo');
  const [protein, setProtein] = useState<File | null>(null);
  const [gro, setGro] = useState<File | null>(null);
  const [itp, setItp] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!protein) {
      setError('A protein (PDB) file is required.');
      return;
    }
    if (mode === 'holo' && (!gro || !itp)) {
      setError('HOLO mode requires a ligand GRO and ITP.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const job =
        mode === 'holo'
          ? await launchSimulateHolo({ protein, ligand_gro: gro!, ligand_itp: itp! }, { max_resources: maxResources })
          : await launchSimulate({ protein }, { max_resources: maxResources });
      notify('success', `MD simulation started (${job.id}) — ${mode.toUpperCase()}.`);
      onDone();
    } catch (err) {
      notify('error', `MD failed: ${(err as Error).message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Panel
      title="GROMACS MD Simulation"
      description="Full molecular dynamics trajectory — APO (protein only) or HOLO (protein + ligand)."
      onSubmit={submit}
      submitting={submitting}
      submitDisabled={!protein || (mode === 'holo' && (!gro || !itp))}
    >
      <div className="flex gap-2 mb-1" role="tablist" aria-label="MD mode">
        {(['apo', 'holo'] as MdMode[]).map((m) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            className={`px-4 py-2 text-sm rounded-md transition-all cursor-pointer border focus-visible:outline focus-visible:outline-accent ${
              mode === m
                ? 'bg-accent text-bg-page border-accent'
                : 'bg-bg-card-hover text-text-secondary border-transparent'
            }`}
            onClick={() => setMode(m)}
          >
            {m === 'apo' ? 'APO — protein only' : 'HOLO — with ligand'}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-4">
        <FileDrop id="md-protein" label="Protein (PDB)" accept=".pdb" file={protein} onFileSelect={setProtein} />
        {mode === 'holo' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-fadeIn">
            <FileDrop id="md-gro" label="Ligand (GRO)" accept=".gro" file={gro} onFileSelect={setGro} />
            <FileDrop id="md-itp" label="Ligand (ITP)" accept=".itp" file={itp} onFileSelect={setItp} />
          </div>
        )}
      </div>
      {error && <FormError message={error} />}
    </Panel>
  );
}