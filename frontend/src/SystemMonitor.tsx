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
    <div className="system-monitor">
      <div className="stat-item">
        <div className="stat-label">CPU</div>
        <div className="stat-bar-container">
          <div className="stat-bar" style={{ width: `${stats.cpu}%` }}></div>
        </div>
        <div className="stat-value">{stats.cpu.toFixed(1)}%</div>
      </div>

      <div className="stat-item">
        <div className="stat-label">RAM</div>
        <div className="stat-bar-container">
          <div className="stat-bar" style={{ width: `${stats.memory}%` }}></div>
        </div>
        <div className="stat-value">{stats.memory.toFixed(1)}%</div>
      </div>

      {stats.gpu && (
        <>
          <div className="stat-item">
            <div className="stat-label">GPU</div>
            <div className="stat-bar-container">
              <div className="stat-bar" style={{ width: `${stats.gpu.utilization}%` }}></div>
            </div>
            <div className="stat-value">{stats.gpu.utilization.toFixed(1)}%</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">VRAM</div>
            <div className="stat-bar-container">
              <div className="stat-bar" style={{ width: `${stats.gpu.memory_percent}%` }}></div>
            </div>
            <div className="stat-value">{Math.round(stats.gpu.memory_used)} MB</div>
          </div>
        </>
      )}
    </div>
  );
}
