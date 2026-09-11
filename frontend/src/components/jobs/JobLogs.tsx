import { useEffect, useRef, useState } from 'react';
import { fetchLogs } from '../../api/client';
import { useJobLogStream } from '../../hooks/useJobLogStream';
import { jobIsTerminal } from '../../hooks/useJobLogStream';
import type { Job } from '../../api/types';
import { PanelLabel } from '../ui/primitives';
import { Button, Spinner } from '../ui/Button';

interface JobLogsProps {
  job: Job;
}

export function JobLogs({ job }: JobLogsProps) {
  const terminal = jobIsTerminal(job.status);
  const live = useJobLogStream(job.id, !terminal);
  const [history, setHistory] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [copied, setCopied] = useState(false);

  const lines = terminal ? history : live.logs.map((l) => l.line);

  useEffect(() => {
    if (!terminal) return;
    let cancelled = false;
    fetchLogs(job.id, 800)
      .then((data) => {
        if (!cancelled) setHistory(data.logs ?? []);
      })
      .catch(() => {
        /* backend unavailable while terminal job is rendered */
      });
    return () => {
      cancelled = true;
    };
  }, [job.id, terminal]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || paused) return;
    el.scrollTop = el.scrollHeight;
  }, [lines, paused]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setPaused(!nearBottom);
  };

  const copyLogs = async () => {
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable in non-secure context */
    }
  };

  return (
    <section className="flex flex-col gap-2 min-h-0 flex-1">
      <div className="flex items-center justify-between">
        <PanelLabel>Console</PanelLabel>
        <div className="flex items-center gap-2">
          {!terminal && (
            <span className="inline-flex items-center gap-1.5 text-[0.7rem] font-mono text-text-secondary">
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  live.connected ? 'bg-accent' : 'bg-warning'
                }`}
              />
              {live.connected ? 'live' : 'connecting'}
            </span>
          )}
          <Button variant="outline" size="sm" onClick={copyLogs}>
            {copied ? 'Copied' : 'Copy logs'}
          </Button>
        </div>
      </div>

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto custom-scrollbar bg-bg-page/60 border border-border rounded-md p-4 font-mono text-[0.82rem] leading-relaxed text-text-primary min-h-[240px]"
        role="log"
      >
        {lines.length === 0 ? (
          <p className="text-text-secondary opacity-70">
            {terminal ? 'No output recorded for this job.' : 'Waiting for pipeline output…'}
          </p>
        ) : (
          lines.map((line, i) => (
            <div key={i} className="flex gap-3 mb-1">
              <span className="text-accent opacity-50 font-bold shrink-0">$</span>
              <span className="whitespace-pre-wrap break-all">{line}</span>
            </div>
          ))
        )}
      </div>

      {!terminal && live.connected && lines.length === 0 && (
        <Spinner className="w-3.5 h-3.5 mx-auto" />
      )}
      {paused && lines.length > 0 && (
        <Button variant="ghost" size="sm" className="self-start" onClick={() => setPaused(false)}>
          Resume autoscroll
        </Button>
      )}
    </section>
  );
}