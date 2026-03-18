import apiClient from './client';
import type { Post } from './types';

export interface PostPriorityConfig {
  id: number;
  post_number: number;
  priority: number;
}

export async function getPostPriorities(): Promise<PostPriorityConfig[]> {
  const res = await apiClient.get<PostPriorityConfig[]>('/api/post-priorities');
  return res.data;
}

export async function updatePostPriority(
  postNumber: number,
  priority: number,
): Promise<PostPriorityConfig> {
  const res = await apiClient.put<PostPriorityConfig>(
    `/api/post-priorities/${postNumber}`,
    { priority },
  );
  return res.data;
}

export async function getPosts(siegeId: number): Promise<Post[]> {
  const res = await apiClient.get<Post[]>(`/api/sieges/${siegeId}/posts`);
  return res.data;
}

export async function updatePost(
  siegeId: number,
  postId: number,
  data: { priority?: number; description?: string | null },
): Promise<Post> {
  const res = await apiClient.put<Post>(`/api/sieges/${siegeId}/posts/${postId}`, data);
  return res.data;
}

export async function setPostConditions(
  siegeId: number,
  postId: number,
  condition_ids: number[],
): Promise<Post> {
  const res = await apiClient.put<Post>(
    `/api/sieges/${siegeId}/posts/${postId}/conditions`,
    { condition_ids },
  );
  return res.data;
}
