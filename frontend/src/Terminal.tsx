import { useEffect, useRef, useState } from 'react';

interface TerminalProps {
  jobId: string;
  onClose: () => void;
  apiBase: string;
}

export function Terminal({ jobId, onClose, apiBase }: TerminalProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${apiBase}/jobs/${jobId}/logs`);
      if (!res.ok) throw new Error('Failed to fetch logs');
      const data = await res.json();
      setLogs(data.logs || []);
    } catch (err) {
      console.error('Error fetching logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="fixed inset-0 bg-black/85 backdrop-blur-[4px] z-[1000] flex items-center justify-center p-8" onClick={onClose}>
      <div className="w-full max-w-[1000px] h-[80vh] flex flex-col bg-bg-card border border-border rounded-lg shadow-[0_20px_25px_-5px_rgba(0,0,0,0.4)] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="bg-bg-page p-2 px-4 flex items-center border-b border-border">
          <div className="flex-1 text-left text-[0.75rem] text-accent font-mono opacity-80 uppercase tracking-widest">
            BIMOS CORE // CONSOLE // ID_{jobId.substring(0, 8).toUpperCase()}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 font-mono text-[0.85rem] leading-relaxed text-text-primary custom-scrollbar">
          {loading && logs.length === 0 ? (
            <div className="flex gap-3 mb-1.5 animate-pulse">
              <span className="text-accent opacity-50">$</span> Connecting to job output...
            </div>
          ) : logs.length === 0 ? (
            <div className="flex gap-3 mb-1.5">
              <span className="text-accent opacity-50">$</span> Waiting for output...
            </div>
          ) : (
            logs.map((line, i) => (
              <div key={i} className="flex gap-3 mb-1.5">
                <span className="text-accent opacity-50 font-bold">$</span> {line}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
