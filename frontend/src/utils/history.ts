const MAX_POINTS = 36;

const history: Record<'cpu' | 'memory' | 'gpu' | 'vram', number[]> = {
  cpu: [],
  memory: [],
  gpu: [],
  vram: [],
};

export function recordStats(s: {
  cpu: number;
  memory: number;
  gpuUtil: number;
  vramPct: number;
}): void {
  history.cpu = push(history.cpu, s.cpu);
  history.memory = push(history.memory, s.memory);
  history.gpu = push(history.gpu, s.gpuUtil);
  history.vram = push(history.vram, s.vramPct);
}

export function getStatsSeries(): typeof history {
  return history;
}

function push(arr: number[], value: number): number[] {
  return [...arr.slice(-(MAX_POINTS - 1)), value];
}