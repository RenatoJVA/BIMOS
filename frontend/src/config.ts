/** Maps UI flow ids to backend process config names. */
export const FLOW_CONFIG_KEY: Record<string, string> = {
  predict: 'esmfold',
  dock: 'docking',
  qm: 'orca',
  md: 'md',
};

export interface ProcessConfigInfo {
  profile: 'default' | 'custom' | 'max';
  custom: boolean;
  path: string;
}

export interface ConfigProfilesResponse {
  config_dir: string;
  processes: Record<string, ProcessConfigInfo>;
}

export async function fetchConfigProfiles(
  apiBase: string,
  previewMax = false,
): Promise<ConfigProfilesResponse | null> {
  const url = previewMax
    ? `${apiBase}/config/profiles?preview_max=true`
    : `${apiBase}/config/profiles`;
  const res = await fetch(url);
  if (!res.ok) return null;
  return res.json();
}
