import { http, HttpResponse } from 'msw';
import type { BuildingTypeInfo } from '../api/types';

const buildingTypes: BuildingTypeInfo[] = [
  { value: 'stronghold',    display: 'Stronghold',    count: 1, base_group_count: 4, base_last_group_slots: 3 },
  { value: 'mana_shrine',   display: 'Mana Shrine',   count: 2, base_group_count: 2, base_last_group_slots: 3 },
  { value: 'magic_tower',   display: 'Magic Tower',   count: 4, base_group_count: 1, base_last_group_slots: 2 },
  { value: 'defense_tower', display: 'Defense Tower', count: 5, base_group_count: 1, base_last_group_slots: 2 },
  { value: 'post',          display: 'Post',          count: 18, base_group_count: 1, base_last_group_slots: 1 },
];

export const handlers = [
  http.get('/api/sieges', () => HttpResponse.json([])),
  http.get('/api/members', () => HttpResponse.json([])),
  http.get('/api/sieges/building-types', () => HttpResponse.json(buildingTypes)),
  http.get('/api/post-conditions', () => HttpResponse.json([])),
];
