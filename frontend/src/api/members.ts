import apiClient from './client';
import type { Member, PostCondition, MemberRoleInfo } from './types';

export async function getMembers(params?: { is_active?: boolean }): Promise<Member[]> {
  const res = await apiClient.get<Member[]>('/api/members', { params });
  return res.data;
}

export async function getMember(id: number): Promise<Member> {
  const res = await apiClient.get<Member>(`/api/members/${id}`);
  return res.data;
}

export async function createMember(data: {
  name: string;
  discord_username?: string | null;
  role: string;
  power_level?: string | null;
}): Promise<Member> {
  const res = await apiClient.post<Member>('/api/members', data);
  return res.data;
}

export async function updateMember(
  id: number,
  data: {
    name?: string;
    discord_username?: string | null;
    role?: string;
    power_level?: string | null;
    is_active?: boolean;
  },
): Promise<Member> {
  const res = await apiClient.put<Member>(`/api/members/${id}`, data);
  return res.data;
}

export async function deleteMember(id: number): Promise<void> {
  await apiClient.delete(`/api/members/${id}`);
}

export async function getMemberPreferences(id: number): Promise<PostCondition[]> {
  const res = await apiClient.get<PostCondition[]>(`/api/members/${id}/preferences`);
  return res.data;
}

export async function updateMemberPreferences(
  id: number,
  condition_ids: number[],
): Promise<PostCondition[]> {
  const res = await apiClient.put<PostCondition[]>(`/api/members/${id}/preferences`, {
    post_condition_ids: condition_ids,
  });
  return res.data;
}

export async function getPostConditions(): Promise<PostCondition[]> {
  const res = await apiClient.get<PostCondition[]>('/api/post-conditions');
  return res.data;
}

export async function getMemberRoles(): Promise<MemberRoleInfo[]> {
  const res = await apiClient.get<MemberRoleInfo[]>('/api/members/roles');
  return res.data;
}
