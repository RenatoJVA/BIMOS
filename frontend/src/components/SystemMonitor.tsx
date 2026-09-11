import { useSystemStats } from '../hooks/useQueries';
import { getStatsSeries } from '../utils/history';
import { formatBytes } from '../utils/format';

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const width = 96;
  const height = 22;

  if (data.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * (width - 2) + 1;
      const y = height - 2 - ((v - min) / span) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} aria-hidden="true" className="block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.4}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Metric({
  label,
  value,
  percent,
  series,
  color,
}: {
  label: string;
  value: string;
  percent: number;
  series: number[];
  color: string;
}) {
  return (
    <div className="flex flex-col gap-1 min-w-[150px]">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[0.7rem] text-text-secondary uppercase tracking-widest">{label}</span>
        <span className="font-mono text-[0.78rem] text-text-primary font-medium">{value}</span>
      </div>
      <div className="h-1 bg-border w-full rounded-[2px] overflow-hidden">
        <div
          className="h-full transition-[width] duration-500 ease-in-out"
          style={{ width: `${Math.min(100, percent)}%`, backgroundColor: color }}
        />
      </div>
      <Sparkline data={series} color={color} />
    </div>
  );
}

export function SystemMonitor() {
  const { data } = useSystemStats();
  if (!data) return null;
  const series = getStatsSeries();

  return (
    <div className="flex gap-6">
      <Metric label="CPU" value={`${data.cpu.toFixed(1)}%`} percent={data.cpu} series={series.cpu} color="var(--accent)" />
      <Metric label="RAM" value={`${data.memory.toFixed(1)}%`} percent={data.memory} series={series.memory} color="var(--accent)" />
      {data.gpu && (
        <>
          <Metric
            label="GPU"
            value={`${data.gpu.utilization.toFixed(1)}%`}
            percent={data.gpu.utilization}
            series={series.gpu}
            color="var(--success)"
          />
          <Metric
            label="VRAM"
            value={`${formatBytes(data.gpu.memory_used)} / ${formatBytes(data.gpu.memory_total)}`}
            percent={data.gpu.memory_percent}
            series={series.vram}
            color="var(--success)"
          />
        </>
      )}
    </div>
  );
}