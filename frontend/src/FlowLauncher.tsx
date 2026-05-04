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
  
  // QM states
  const [groFile, setGroFile] = useState<File | null>(null);
  const [itpFile, setItpFile] = useState<File | null>(null);
  const [charge, setCharge] = useState(0);

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

  return (
    <div className="flow-launcher">
      <div className="flow-selector">
        <button 
          className={`flow-btn ${activeFlow === 'predict' ? 'active' : ''}`}
          onClick={() => setActiveFlow('predict')}
        >
          Predict
        </button>
        <button 
          className={`flow-btn ${activeFlow === 'dock' ? 'active' : ''}`}
          onClick={() => setActiveFlow('dock')}
        >
          Dock
        </button>
        <button 
          className={`flow-btn ${activeFlow === 'qm' ? 'active' : ''}`}
          onClick={() => setActiveFlow('qm')}
        >
          QM Dynamics
        </button>
      </div>

      {activeFlow === 'predict' && (
        <form className="glass-card flow-form" onSubmit={startPredict}>
          <h3>ESMFold Prediction</h3>
          <input 
            type="text" 
            placeholder="Job Name" 
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <textarea 
            placeholder="Fasta sequence..." 
            value={fasta}
            onChange={(e) => setFasta(e.target.value)}
            required
          />
          <button type="submit" disabled={loading}>Launch Job</button>
        </form>
      )}

      {activeFlow === 'dock' && (
        <form className="glass-card flow-form" onSubmit={startDock}>
          <h3>Vina Docking</h3>
          <div className="flow-grid">
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
          <button type="submit" disabled={loading}>Launch Job</button>
        </form>
      )}

      {activeFlow === 'qm' && (
        <form className="glass-card flow-form" onSubmit={startQM}>
          <h3>ORCA QM Pipeline</h3>
          <div className="flow-grid">
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
          <div className="input-group">
            <label>Total Charge</label>
            <input 
              type="number" 
              value={charge} 
              onChange={(e) => setCharge(parseInt(e.target.value))} 
            />
          </div>
          <button type="submit" disabled={loading}>Launch Job</button>
        </form>
      )}
    </div>
  );
}
