import { useState } from 'react';
import { FileDrop } from './FileDrop';

interface FlowLauncherProps {
  apiBase: string;
  onJobStarted: () => void;
}

export function FlowLauncher({ apiBase, onJobStarted }: FlowLauncherProps) {
  const [activeFlow, setActiveFlow] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [fasta, setFasta] = useState('');
  const [proteinFile, setProteinFile] = useState<File | null>(null);
  const [ligandsFile, setLigandsFile] = useState<File | null>(null);
  
  // QM / MD states
  const [groFile, setGroFile] = useState<File | null>(null);
  const [itpFile, setItpFile] = useState<File | null>(null);
  const [charge, setCharge] = useState(0);
  const [mdType, setMdType] = useState<'apo' | 'holo'>('apo');

  const startPredict = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fasta_content: fasta, name: name || 'protein_job' }),
      });
      if (res.ok) {
        setActiveFlow(null);
        setFasta('');
        setName('');
        onJobStarted();
      }
    } catch (err) {
      alert('Error starting prediction');
    } finally {
      setLoading(false);
    }
  };

  const startDock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proteinFile || !ligandsFile) return;
    setLoading(true);
    const formData = new FormData();
    formData.append('protein', proteinFile);
    formData.append('ligands', ligandsFile);

    try {
      const res = await fetch(`${apiBase}/dock`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        setActiveFlow(null);
        setProteinFile(null);
        setLigandsFile(null);
        onJobStarted();
      }
    } catch (err) {
      alert('Error starting docking');
    } finally {
      setLoading(false);
    }
  };

  const startQM = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!groFile || !itpFile) return;
    setLoading(true);
    const formData = new FormData();
    formData.append('gro', groFile);
    formData.append('itp', itpFile);
    formData.append('charge', String(charge));

    try {
      const res = await fetch(`${apiBase}/qm-orca-files`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        setActiveFlow(null);
        setGroFile(null);
        setItpFile(null);
        onJobStarted();
      }
    } catch (err) {
      alert('Error starting QM pipeline');
    } finally {
      setLoading(false);
    }
  };

  const startMD = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proteinFile) return;
    if (mdType === 'holo' && (!groFile || !itpFile)) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('protein', proteinFile);
    
    let endpoint = `${apiBase}/simulate`;
    if (mdType === 'holo') {
      endpoint = `${apiBase}/simulate-holo`;
      formData.append('ligand_gro', groFile!);
      formData.append('ligand_itp', itpFile!);
    }

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        setActiveFlow(null);
        setProteinFile(null);
        setGroFile(null);
        setItpFile(null);
        onJobStarted();
      }
    } catch (err) {
      alert('Error starting MD simulation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mb-12 animate-[fadeIn_0.6s_ease-out]">
      <div className="flex gap-4 mb-6">
        <button 
          className={`px-5 py-2.5 rounded-lg border font-medium text-[0.85rem] transition-all duration-200 cursor-pointer ${
            activeFlow === 'predict' 
              ? 'bg-accent text-bg-page border-accent font-semibold' 
              : 'bg-bg-card border-border text-text-secondary hover:border-border-active hover:text-text-primary'
          }`}
          onClick={() => setActiveFlow('predict')}
        >
          Predict
        </button>
        <button 
          className={`px-5 py-2.5 rounded-lg border font-medium text-[0.85rem] transition-all duration-200 cursor-pointer ${
            activeFlow === 'dock' 
              ? 'bg-accent text-bg-page border-accent font-semibold' 
              : 'bg-bg-card border-border text-text-secondary hover:border-border-active hover:text-text-primary'
          }`}
          onClick={() => setActiveFlow('dock')}
        >
          Dock
        </button>
        <button 
          className={`px-5 py-2.5 rounded-lg border font-medium text-[0.85rem] transition-all duration-200 cursor-pointer ${
            activeFlow === 'qm' 
              ? 'bg-accent text-bg-page border-accent font-semibold' 
              : 'bg-bg-card border-border text-text-secondary hover:border-border-active hover:text-text-primary'
          }`}
          onClick={() => setActiveFlow('qm')}
        >
          QM Dynamics
        </button>
        <button 
          className={`px-5 py-2.5 rounded-lg border font-medium text-[0.85rem] transition-all duration-200 cursor-pointer ${
            activeFlow === 'md' 
              ? 'bg-accent text-bg-page border-accent font-semibold' 
              : 'bg-bg-card border-border text-text-secondary hover:border-border-active hover:text-text-primary'
          }`}
          onClick={() => setActiveFlow('md')}
        >
          Molecular Dynamics
        </button>
      </div>

      {activeFlow && (
        <form 
          className="bg-bg-card border border-border rounded-lg p-6 flex flex-col gap-6 shadow-sm animate-[fadeIn_0.4s_ease-out]" 
          onSubmit={
            activeFlow === 'predict' ? startPredict : 
            activeFlow === 'dock' ? startDock : 
            activeFlow === 'qm' ? startQM : startMD
          }
        >
          <h3 className="text-xl font-bold text-accent capitalize">
            {activeFlow === 'predict' ? 'ESMFold Prediction' : 
             activeFlow === 'dock' ? 'Vina Docking' : 
             activeFlow === 'qm' ? 'ORCA QM Pipeline' : 'GROMACS MD Simulation'}
          </h3>
          
          {activeFlow === 'predict' && (
            <>
              <input 
                type="text" 
                placeholder="Job Name" 
                className="bg-bg-card border border-border text-text-primary p-4 font-mono text-[0.9rem] rounded focus:outline-none focus:border-accent focus:bg-bg-card-hover transition-all"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <textarea 
                placeholder="Fasta sequence..." 
                className="bg-bg-card border border-border text-text-primary p-4 font-mono text-[0.9rem] rounded focus:outline-none focus:border-accent focus:bg-bg-card-hover transition-all min-h-[150px] resize-y"
                value={fasta}
                onChange={(e) => setFasta(e.target.value)}
                required
              />
            </>
          )}

          {activeFlow === 'dock' && (
            <div className="grid grid-cols-2 gap-4">
              <FileDrop 
                label="Protein (PDB)" 
                accept=".pdb" 
                file={proteinFile} 
                onFileSelect={setProteinFile} 
              />
              <FileDrop 
                label="Ligands (SDF)" 
                accept=".sdf" 
                file={ligandsFile} 
                onFileSelect={setLigandsFile} 
              />
            </div>
          )}

          {activeFlow === 'qm' && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <FileDrop 
                  label="Structure (GRO)" 
                  accept=".gro" 
                  file={groFile} 
                  onFileSelect={setGroFile} 
                />
                <FileDrop 
                  label="Topology (ITP)" 
                  accept=".itp" 
                  file={itpFile} 
                  onFileSelect={setItpFile} 
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="font-mono text-[0.75rem] text-text-secondary uppercase">Total Charge</label>
                <input 
                  type="number" 
                  className="bg-bg-card border border-border text-text-primary p-2 rounded focus:outline-none focus:border-accent"
                  value={charge} 
                  onChange={(e) => setCharge(parseInt(e.target.value))} 
                />
              </div>
            </>
          )}

          {activeFlow === 'md' && (
            <>
              <div className="flex gap-4 mb-2">
                <button 
                  type="button"
                  className={`px-4 py-2 text-sm rounded transition-all ${mdType === 'apo' ? 'bg-accent text-bg-page' : 'bg-bg-card-hover text-text-secondary'}`}
                  onClick={() => setMdType('apo')}
                >Apo (Protein Only)</button>
                <button 
                  type="button"
                  className={`px-4 py-2 text-sm rounded transition-all ${mdType === 'holo' ? 'bg-accent text-bg-page' : 'bg-bg-card-hover text-text-secondary'}`}
                  onClick={() => setMdType('holo')}
                >Holo (Protein + Ligand)</button>
              </div>

              <div className="grid grid-cols-1 gap-4">
                <FileDrop 
                  label="Protein (PDB)" 
                  accept=".pdb" 
                  file={proteinFile} 
                  onFileSelect={setProteinFile} 
                />
                {mdType === 'holo' && (
                  <div className="grid grid-cols-2 gap-4">
                    <FileDrop 
                      label="Ligand (GRO)" 
                      accept=".gro" 
                      file={groFile} 
                      onFileSelect={setGroFile} 
                    />
                    <FileDrop 
                      label="Ligand (ITP)" 
                      accept=".itp" 
                      file={itpFile} 
                      onFileSelect={setItpFile} 
                    />
                  </div>
                )}
              </div>
            </>
          )}

          <button 
            type="submit" 
            className="bg-accent text-bg-page border-none p-3 font-bold cursor-pointer rounded transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={loading}
          >
            {loading ? 'Launching...' : 'Launch Job'}
          </button>
        </form>
      )}
    </div>
  );
}
