import { useEffect, useState } from 'react';

interface Stats {
  cpu: number;
  memory: number;
  gpu: {
    utilization: number;
    memory_used: number;
    memory_total: number;
    memory_percent: number;
  } | null;
}

export function SystemMonitor({ apiBase }: { apiBase: string }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${apiBase}/system/stats`);
        const data = await res.json();
        setStats(data);
      } catch (e) {
        console.error('Failed to fetch system stats');
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 2000);
    return () => clearInterval(interval);
  }, [apiBase]);

  if (!stats) return null;

  return (
    <div className="flex gap-6">
      <div className="flex flex-col gap-1 min-w-[120px]">
        <div className="font-mono text-[0.7rem] text-text-secondary uppercase tracking-widest">CPU</div>
        <div className="h-1 bg-border w-full rounded-[2px] overflow-hidden">
          <div className="h-full bg-accent transition-[width] duration-500 ease-in-out" style={{ width: `${stats.cpu}%` }}></div>
        </div>
        <div className="font-mono text-[0.85rem] text-text-primary font-medium">{stats.cpu.toFixed(1)}%</div>
      </div>

      <div className="flex flex-col gap-1 min-w-[120px]">
        <div className="font-mono text-[0.7rem] text-text-secondary uppercase tracking-widest">RAM</div>
        <div className="h-1 bg-border w-full rounded-[2px] overflow-hidden">
          <div className="h-full bg-accent transition-[width] duration-500 ease-in-out" style={{ width: `${stats.memory}%` }}></div>
        </div>
        <div className="font-mono text-[0.85rem] text-text-primary font-medium">{stats.memory.toFixed(1)}%</div>
      </div>

      {stats.gpu && (
        <>
          <div className="flex flex-col gap-1 min-w-[120px]">
            <div className="font-mono text-[0.7rem] text-text-secondary uppercase tracking-widest">GPU</div>
            <div className="h-1 bg-border w-full rounded-[2px] overflow-hidden">
              <div className="h-full bg-accent transition-[width] duration-500 ease-in-out" style={{ width: `${stats.gpu.utilization}%` }}></div>
            </div>
            <div className="font-mono text-[0.85rem] text-text-primary font-medium">{stats.gpu.utilization.toFixed(1)}%</div>
          </div>
          <div className="flex flex-col gap-1 min-w-[120px]">
            <div className="font-mono text-[0.7rem] text-text-secondary uppercase tracking-widest">VRAM</div>
            <div className="h-1 bg-border w-full rounded-[2px] overflow-hidden">
              <div className="h-full bg-accent transition-[width] duration-500 ease-in-out" style={{ width: `${stats.gpu.memory_percent}%` }}></div>
            </div>
            <div className="font-mono text-[0.85rem] text-text-primary font-medium">{Math.round(stats.gpu.memory_used)} MB</div>
          </div>
        </>
      )}
    </div>
  );
}
