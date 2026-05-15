import { useEffect, useState } from 'react';
import { Terminal } from './Terminal';
import { SystemMonitor } from './SystemMonitor';
import { FlowLauncher } from './FlowLauncher';

const API_BASE = 'http://localhost:8000/api/v1';

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
  results?: any;
}

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [systemTheme, setSystemTheme] = useState<'light' | 'dark' | null>(null);

  // Initial theme detection from URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromUrl = params.get('systemTheme') as 'light' | 'dark' | null;
    if (fromUrl) setSystemTheme(fromUrl);
  }, []);

  // Poll backend for system theme changes (for live updates in Qt)
  useEffect(() => {
    const pollTheme = async () => {
      try {
        const res = await fetch(`${API_BASE}/system/theme`);
        if (res.ok) {
          const data = await res.json();
          setSystemTheme(data.theme);
        }
      } catch (e) {
        // Fallback to matchMedia if API is down
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setSystemTheme(prefersDark ? 'dark' : 'light');
      }
    };

    pollTheme();
    const interval = setInterval(pollTheme, 1000); // Check every 1 second
    return () => clearInterval(interval);
  }, []);

  // Apply the effective theme to the <html> element
  useEffect(() => {
    const root = document.documentElement;
    const effective = systemTheme || 'light';
    root.setAttribute('data-theme', effective);
  }, [systemTheme]);

  // Browser-native fallback listener (for real browsers)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      setSystemTheme(e.matches ? 'dark' : 'light');
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);


  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs`);
      if (!res.ok) throw new Error('Failed to fetch jobs');
      const data = await res.json();
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
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const formatMeta = (meta: Record<string, any>) => {
    return Object.entries(meta)
      .map(([k, v]) => {
        const valStr = String(v);
        const displayVal = valStr.includes('/') ? valStr.split('/').pop() : valStr;
        return `${k}: ${displayVal}`;
      })
      .join(' | ');
  };

  return (
    <div className="min-h-screen bg-bg-page text-text-primary transition-colors duration-200">
      <div className="max-w-[1200px] mx-auto p-8 w-full animate-fadeIn">
        <header className="mb-12 flex justify-between items-center border-b border-border pb-6">
          <div className="flex flex-col gap-2">
            <h1 className="text-4xl font-bold tracking-tight text-text-primary">BIMOS Dashboard</h1>
            <p className="text-text-secondary text-base font-mono tracking-widest uppercase opacity-80">
              Biomolecular Modeling Suite • Live Job Monitor
            </p>
          </div>
          <SystemMonitor apiBase={API_BASE} />
        </header>


        <main>
          <FlowLauncher apiBase={API_BASE} onJobStarted={fetchJobs} />
          {loading ? (
            <div className="text-center py-32 text-text-secondary font-mono border border-dashed border-border rounded-lg bg-bg-card/30">
              <div className="w-10 h-10 border border-accent border-t-transparent animate-spin mx-auto mb-8"></div>
              <p>Connecting to backend engine...</p>
            </div>
          ) : error ? (
            <div className="bg-bg-card border border-danger rounded-lg p-6">
              <p className="text-danger font-mono text-sm">{error}</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="bg-bg-card/30 border border-dashed border-border rounded-lg p-32 text-center text-text-secondary font-mono">
              <p>No active jobs.</p>
              <p className="text-sm mt-2 opacity-60">
                Run jobs via CLI: <code className="bg-bg-card px-2 py-1 rounded">bimos predict --background</code>
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(400px,1fr))] gap-4">
              {jobs.map((job) => (
                <div 
                  key={job.id} 
                  className="bg-bg-card border border-border rounded-lg p-6 transition-all duration-200 relative shadow-sm hover:border-border-active hover:shadow-md flex flex-col gap-4 cursor-pointer active:translate-y-[1px]"
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex flex-col gap-2">
                      <div className="font-mono text-xs text-accent opacity-70">ID_{job.id.substring(0, 8).toUpperCase()}</div>
                      <div className="text-[1.15rem] font-semibold text-text-primary capitalize leading-none">{job.kind.replace('-', ' ')}</div>
                    </div>
                    <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-[2px] text-[0.75rem] font-mono font-medium border ${
                      job.status === 'running' ? 'text-accent bg-accent-glow border-accent' :
                      job.status === 'completed' ? 'text-success bg-transparent border-success' :
                      job.status === 'failed' ? 'text-danger bg-transparent border-danger' :
                      'text-warning bg-transparent border-warning'
                    }`}>
                      {job.status}
                    </span>
                  </div>

                  <div className="text-[0.85rem] text-text-secondary font-mono leading-relaxed">
                    {formatMeta(job.meta)}
                  </div>

                  {job.results && job.kind === 'dock' && Array.isArray(job.results) && (
                    <div className="border-t border-border pt-4 mt-2 bg-bg-page/50 -mx-6 px-6 -mb-6 pb-6 rounded-b-lg">
                      <div className="text-[0.7rem] uppercase tracking-widest text-accent mb-3 font-bold">Top Docking Hits</div>
                      <div className="flex flex-col gap-2">
                        {job.results.slice(0, 3).map((res: any, i: number) => (
                          <div key={i} className="flex justify-between items-center bg-bg-card border border-border p-2 rounded text-[0.8rem] font-mono shadow-sm">
                            <span className="truncate flex-1 pr-2 opacity-90">{res.complex.split('-').pop()}</span>
                            <span className="text-success font-bold">{res.best_score_kcal_mol.toFixed(2)} kcal/mol</span>
                          </div>
                        ))}
                        {job.results.length > 3 && (
                          <div className="text-[0.65rem] text-center text-text-secondary opacity-60 mt-1">
                            + {job.results.length - 3} more results in output directory
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {(job.output_dir || job.error) && !job.results && (
                    <div className="border-t border-border pt-4 mt-2 text-[0.75rem] opacity-80 font-mono flex flex-col gap-1">
                      {job.error ? (
                        <span className="text-danger">ERROR: {job.error}</span>
                      ) : (
                        <span className="text-text-secondary truncate" title={job.output_dir}>OUTPUT: {job.output_dir}</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

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
