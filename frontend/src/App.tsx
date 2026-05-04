import { useEffect, useState } from 'react';
import { Terminal } from './Terminal';

const API_BASE = 'http://localhost:8000/api/v1';

// Same structure as JobResponse in backend
interface Job {
  id: string;
  kind: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at?: string;
  finished_at?: string;
  error?: string;
  output_dir?: string;
  meta: Record<string, any>;
}

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs`);
      if (!res.ok) throw new Error('Failed to fetch jobs');
      const data = await res.json();
      // Sort newest first
      setJobs(data.sort((a: Job, b: Job) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      ));
      setError(null);
    } catch (err: any) {
      setError('Could not connect to BIMOS Backend. Is it running? (python main.py gui)');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    // Poll every 3 seconds for live updates
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const formatMeta = (meta: Record<string, any>) => {
    return Object.entries(meta)
      .map(([k, v]) => {
        // Only show base filename instead of full path for cleaner UI
        const valStr = String(v);
        const displayVal = valStr.includes('/') ? valStr.split('/').pop() : valStr;
        return `${k}: ${displayVal}`;
      })
      .join(' | ');
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1 className="title">BIMOS Dashboard</h1>
        <p className="subtitle">Biomolecular Modeling Suite • Live Job Monitor</p>
      </header>

      <main>
        {loading ? (
          <div className="empty-state">
            <div className="spinner"></div>
            <p>Connecting to backend engine...</p>
          </div>
        ) : error ? (
          <div className="glass-card" style={{ borderColor: 'var(--danger)' }}>
            <p style={{ color: 'var(--danger)' }}>{error}</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="glass-card empty-state">
            <p>No active jobs.</p>
            <p style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
              Run jobs via CLI: <code>bimos predict --background</code>
            </p>
          </div>
        ) : (
          <div className="dashboard-grid">
            {jobs.map((job) => (
              <div 
                key={job.id} 
                className="glass-card job-item"
                onClick={() => setSelectedJobId(job.id)}
              >
                <div className="job-header">
                  <div className="job-info">
                    <div className="job-id">ID_{job.id.substring(0, 8).toUpperCase()}</div>
                    <div className="job-kind">{job.kind.replace('-', ' ')}</div>
                  </div>
                  <span className={`status-badge status-${job.status}`}>
                    {job.status}
                  </span>
                </div>

                <div className="job-meta">
                  {formatMeta(job.meta)}
                </div>

                {(job.output_dir || job.error) && (
                  <div className="job-meta" style={{ 
                    borderTop: '1px solid var(--border)', 
                    paddingTop: '0.5rem',
                    fontSize: '0.75rem',
                    opacity: 0.8
                  }}>
                    {job.error ? (
                      <span style={{ color: 'var(--danger)' }}>ERROR: {job.error}</span>
                    ) : (
                      <span>OUTPUT: {job.output_dir}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {selectedJobId && (
        <Terminal 
          jobId={selectedJobId} 
          onClose={() => setSelectedJobId(null)} 
          apiBase={API_BASE}
        />
      )}
    </div>
  );
}

export default App;
