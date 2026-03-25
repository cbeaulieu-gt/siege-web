import { useQuery } from '@tanstack/react-query';
import apiClient from './client';
import type { VersionInfo } from './types';

async function getVersion(): Promise<VersionInfo> {
  const res = await apiClient.get<VersionInfo>('/api/version');
  return res.data;
}

export function useVersion() {
  return useQuery({
    queryKey: ['version'],
    queryFn: getVersion,
    // Version info is stable — refetch only on manual invalidation or mount.
    staleTime: 5 * 60 * 1000,
  });
}
