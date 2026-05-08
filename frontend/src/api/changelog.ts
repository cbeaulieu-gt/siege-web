import apiClient from "./client";

export interface ChangelogStatus {
  last_seen_changelog_at: string | null;
}

export async function fetchChangelogStatus(): Promise<ChangelogStatus> {
  const res = await apiClient.get<ChangelogStatus>("/api/changelog/status");
  return res.data;
}

export async function markChangelogSeen(): Promise<ChangelogStatus> {
  const res = await apiClient.post<ChangelogStatus>("/api/changelog/mark-seen");
  return res.data;
}
