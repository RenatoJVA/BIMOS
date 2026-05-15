import { useEffect, useState } from 'react';
import {
  fetchConfigProfiles,
  FLOW_CONFIG_KEY,
  type ConfigProfilesResponse,
} from './config';

interface ConfigBarProps {
  apiBase: string;
  activeFlow: string | null;
  maxResources: boolean;
  onMaxResourcesChange: (value: boolean) => void;
}

function effectiveProfile(profile: string, maxResources: boolean): string {
  return maxResources ? 'max' : profile;
}

export function ConfigBar({
  apiBase,
  activeFlow,
  maxResources,
  onMaxResourcesChange,
}: ConfigBarProps) {
  const [configs, setConfigs] = useState<ConfigProfilesResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const data = await fetchConfigProfiles(apiBase, maxResources);
      if (!cancelled) setConfigs(data);
    };
    load();
    const interval = setInterval(load, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [apiBase, maxResources]);

  const processKey = activeFlow ? FLOW_CONFIG_KEY[activeFlow] : null;
  const active = processKey && configs?.processes[processKey];

  return (
    <div className="mb-6 bg-bg-card border border-border rounded-lg p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[0.7rem] uppercase tracking-widest text-text-secondary font-mono">
            Pipeline configuration
          </span>
          <span className="text-sm text-text-primary">
            Jobs use YAML from{' '}
            <code className="text-accent text-xs bg-bg-page px-1.5 py-0.5 rounded">
              {configs?.config_dir ?? '~/.bimos/config'}
            </code>
          </span>
        </div>
        <label className="flex items-center gap-2 cursor-pointer select-none text-sm font-mono">
          <input
            type="checkbox"
            checked={maxResources}
            onChange={(e) => onMaxResourcesChange(e.target.checked)}
            className="accent-accent w-4 h-4"
          />
          Max resources
        </label>
      </div>

      {activeFlow && active && (
        <div className="flex flex-wrap items-center gap-2 text-[0.8rem] font-mono border-t border-border pt-3">
          <span className="text-text-secondary">Active flow:</span>
          <span className="capitalize text-text-primary">{activeFlow}</span>
          <span
            className={`px-2 py-0.5 rounded border text-[0.7rem] uppercase tracking-wide ${
              effectiveProfile(active.profile, maxResources) === 'custom'
                ? 'border-warning text-warning'
                : effectiveProfile(active.profile, maxResources) === 'max'
                  ? 'border-accent text-accent'
                  : 'border-border text-text-secondary'
            }`}
          >
            {effectiveProfile(active.profile, maxResources)}
          </span>
          {active.custom && !maxResources && (
            <span className="text-text-secondary opacity-80">
              (edited — not using packaged defaults)
            </span>
          )}
          {maxResources && (
            <span className="text-text-secondary opacity-80">
              (max CPU / memory overrides applied on launch)
            </span>
          )}
        </div>
      )}

      {!activeFlow && configs && (
        <div className="flex flex-wrap gap-2 border-t border-border pt-3">
          {Object.entries(configs.processes).map(([name, info]) => (
            <span
              key={name}
              className="text-[0.65rem] font-mono px-2 py-1 rounded border border-border text-text-secondary"
              title={info.path}
            >
              {name}: {info.custom ? 'custom' : 'default'}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
