import { useConfigProfiles } from '../../hooks/useQueries';
import { Chip } from '../ui/Chip';

interface ConfigBarProps {
  activeFlow: string | null;
  maxResources: boolean;
  onMaxResourcesChange: (value: boolean) => void;
}

function effectiveProfile(profile: string, maxResources: boolean): string {
  return maxResources ? 'max' : profile;
}

export function ConfigBar({
  activeFlow,
  maxResources,
  onMaxResourcesChange,
}: ConfigBarProps) {
  const { data: configs } = useConfigProfiles(true);
  const processKey =
    activeFlow === 'predict'
      ? 'boltz'
      : activeFlow === 'dock'
        ? 'docking'
        : activeFlow === 'qm'
          ? 'orca'
          : activeFlow === 'md'
            ? 'md'
            : null;
  const active = processKey && configs?.processes[processKey];

  return (
    <div className="mb-6 bg-bg-card border border-border rounded-lg p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-[0.7rem] uppercase tracking-widest text-text-secondary font-mono">
            Pipeline configuration
          </span>
          <span className="text-sm text-text-primary">
            {activeFlow
              ? 'Job settings read from your local configuration profiles.'
              : 'Select a pipeline above to see its active configuration.'}
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
          <Chip
            variant={
              effectiveProfile(active.profile, maxResources) === 'custom'
                ? 'warning'
                : effectiveProfile(active.profile, maxResources) === 'max'
                  ? 'accent'
                  : 'default'
            }
          >
            {effectiveProfile(active.profile, maxResources)}
          </Chip>
          {active.custom && !maxResources && (
            <span className="text-text-secondary opacity-80">Edited from defaults</span>
          )}
          {maxResources && (
            <span className="text-text-secondary opacity-80">max CPU / memory overrides</span>
          )}
        </div>
      )}

      {!activeFlow && configs && (
        <div className="flex flex-wrap gap-2 border-t border-border pt-3">
          {Object.entries(configs.processes).map(([name, info]) => (
            <Chip key={name} title={info.path} variant={info.custom ? 'warning' : 'default'}>
              {name}: {info.custom ? 'custom' : 'default'}
            </Chip>
          ))}
        </div>
      )}
    </div>
  );
}