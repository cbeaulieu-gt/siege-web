import type { BuildingType } from '../api/types';

/** Per-slot color tokens for a building type, used on both the Board and Settings pages. */
export type BuildingColorClass = {
  /** Solid colored header bar (e.g. the left sidebar on a building card). */
  header: string;
  /** Text color matching the header hue, used on light backgrounds. */
  headerText: string;
  /** Border color for the card outline and internal dividers. */
  border: string;
  /** Light tinted background for group cells. */
  bg: string;
  /** Section header row (collapsible building-type heading). */
  sectionHeader: string;
};

export const BUILDING_COLORS: Record<BuildingType, BuildingColorClass> = {
  stronghold: {
    header: 'bg-red-600',
    headerText: 'text-red-700',
    border: 'border-red-200',
    bg: 'bg-red-50',
    sectionHeader: 'bg-red-50 border-red-200 text-red-800',
  },
  mana_shrine: {
    header: 'bg-amber-500',
    headerText: 'text-amber-700',
    border: 'border-amber-200',
    bg: 'bg-amber-50',
    sectionHeader: 'bg-amber-50 border-amber-200 text-amber-800',
  },
  magic_tower: {
    header: 'bg-blue-600',
    headerText: 'text-blue-700',
    border: 'border-blue-200',
    bg: 'bg-blue-50',
    sectionHeader: 'bg-blue-50 border-blue-200 text-blue-800',
  },
  defense_tower: {
    header: 'bg-green-600',
    headerText: 'text-green-700',
    border: 'border-green-200',
    bg: 'bg-green-50',
    sectionHeader: 'bg-green-50 border-green-200 text-green-800',
  },
  post: {
    header: 'bg-slate-500',
    headerText: 'text-slate-700',
    border: 'border-slate-200',
    bg: 'bg-slate-50',
    sectionHeader: 'bg-slate-50 border-slate-200 text-slate-800',
  },
};

export const BUILDING_LABELS: Record<BuildingType, string> = {
  stronghold: 'Stronghold',
  mana_shrine: 'Mana Shrine',
  magic_tower: 'Magic Tower',
  defense_tower: 'Defense Tower',
  post: 'Post',
};
