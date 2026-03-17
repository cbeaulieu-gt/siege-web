import apiClient from './client';
import type { BoardResponse, PositionResponse } from './types';

export async function getBoard(siegeId: number): Promise<BoardResponse> {
  const res = await apiClient.get<BoardResponse>(`/api/sieges/${siegeId}/board`);
  return res.data;
}

export async function updatePosition(
  siegeId: number,
  positionId: number,
  data: {
    member_id?: number | null;
    is_reserve?: boolean;
    has_no_assignment?: boolean;
  },
): Promise<PositionResponse> {
  const res = await apiClient.put<PositionResponse>(
    `/api/sieges/${siegeId}/positions/${positionId}`,
    data,
  );
  return res.data;
}
