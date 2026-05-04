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
    <div className="terminal-overlay" onClick={onClose}>
      <div className="terminal-window glass-card" onClick={(e) => e.stopPropagation()}>
        <div className="terminal-header">
          <div className="terminal-controls">
            <span className="control" onClick={onClose}>[CLOSE]</span>
            <span className="control">[MINIMIZE]</span>
            <span className="control">[MAXIMIZE]</span>
          </div>
          <div className="terminal-title">BIMOS CORE // CONSOLE // ID_{jobId.substring(0, 8).toUpperCase()}</div>
        </div>
        <div className="terminal-body">
          {loading && logs.length === 0 ? (
            <div className="terminal-line">Connecting to job output...</div>
          ) : logs.length === 0 ? (
            <div className="terminal-line">Waiting for output...</div>
          ) : (
            logs.map((line, i) => (
              <div key={i} className="terminal-line">
                <span className="terminal-prompt">$</span> {line}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
