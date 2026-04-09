import apiClient from "./client";
import type {
  NotifyResponse,
  NotificationBatchResponse,
  GenerateImagesResponse,
} from "./types";

export async function notifySiegeMembers(
  siegeId: number
): Promise<NotifyResponse> {
  const res = await apiClient.post<NotifyResponse>(
    `/api/sieges/${siegeId}/notify`
  );
  return res.data;
}

export async function getNotificationBatch(
  siegeId: number,
  batchId: number
): Promise<NotificationBatchResponse> {
  const res = await apiClient.get<NotificationBatchResponse>(
    `/api/sieges/${siegeId}/notify/${batchId}`
  );
  return res.data;
}

export async function postToChannel(
  siegeId: number
): Promise<{ status: string; detail?: string }> {
  const res = await apiClient.post(`/api/sieges/${siegeId}/post-to-channel`);
  return res.data;
}

export async function generateImages(
  siegeId: number
): Promise<GenerateImagesResponse> {
  const res = await apiClient.post<GenerateImagesResponse>(
    `/api/sieges/${siegeId}/generate-images`
  );
  return res.data;
}
