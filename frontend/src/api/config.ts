import apiClient from "./client";

export interface AppConfig {
  auth_disabled: boolean;
}

export async function fetchConfig(): Promise<AppConfig> {
  const res = await apiClient.get<AppConfig>("/api/config");
  return res.data;
}
