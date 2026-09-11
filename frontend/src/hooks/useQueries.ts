import { useQuery } from '@tanstack/react-query';
import {
  fetchConfigProfiles,
  fetchJob,
  fetchJobs,
  fetchSystemStats,
} from '../api/client';

export function useJobs() {
  return useQuery({
    queryKey: ['jobs'],
    queryFn: ({ signal }) => fetchJobs(signal),
    refetchInterval: 3000,
  });
}

export function useJob(jobId: string) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: ({ signal }) => fetchJob(jobId, signal),
    refetchInterval: 3000,
  });
}

export function useSystemStats() {
  return useQuery({
    queryKey: ['system-stats'],
    queryFn: ({ signal }) => fetchSystemStats(signal),
    refetchInterval: 2500,
    retry: false,
  });
}

export function useConfigProfiles(enabled: boolean) {
  return useQuery({
    queryKey: ['config-profiles'],
    queryFn: ({ signal }) => fetchConfigProfiles(signal),
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
    enabled,
  });
}