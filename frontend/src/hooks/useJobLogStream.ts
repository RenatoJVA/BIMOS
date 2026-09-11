import { useEffect, useRef, useState } from 'react';
import { jobLogStreamUrl } from '../api/client';
import type { JobStatus } from '../api/types';

export interface StreamedLog {
  line: string;
  ts: number;
}

function parseEvent(data: string): string | null {
  try {
    const parsed = JSON.parse(data);
    if (typeof parsed?.line === 'string') return parsed.line;
    return null;
  } catch {
    return null;
  }
}

export function jobIsTerminal(status: JobStatus): boolean {
  return status === 'completed' || status === 'failed' || status === 'canceled';
}

/**
 * Streams live logs via SSE while enabled. Consumers should remount this hook
 * per job (e.g. with a `key={job.id}`) so the buffer starts empty for new jobs.
 */
export function useJobLogStream(jobId: string, enabled: boolean) {
  const [logs, setLogs] = useState<StreamedLog[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource(jobLogStreamUrl(jobId));
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onmessage = (event) => {
      const line = parseEvent(event.data);
      if (line) setLogs((prev) => [...prev, { line, ts: Date.now() }]);
    };
    es.onerror = () => {
      setConnected(false);
      // EventSource auto-reconnects; no need to tear down here.
    };

    return () => {
      es.close();
      esRef.current = null;
      setConnected(false);
    };
  }, [jobId, enabled]);

  return { logs, connected };
}