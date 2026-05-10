# Handoff: Post Suggestions Modal

## Overview

Redesign of the **Suggest Post Assignments** modal — the dialog a planner opens
to apply algorithm-generated suggestions for which member should hold each
post on a siege board. The redesign replaces the original opaque list with a
structured diff that makes three things obvious at a glance:

1. **What outcome each row falls into** — new assignment, replacement of an
   existing member, already optimal, or skipped.
2. **Which Post Condition** caused the suggestion (the rule that matched).
3. **Which rows the planner has opted into applying** — selection is
   per-row, not all-or-nothing.

## About the design files

The files under `prototype/` are **design references created in HTML** —
prototypes showing intended look and behavior, not production code to copy
directly. The task is to **recreate this design in the target codebase's
existing environment** (React, Vue, etc.) using its established components,
design tokens, and patterns. Treat the JSX in `variation-a.jsx` as a
visual specification, not a drop-in module.

## Fidelity

**High-fidelity.** Spacing, type scale, color tones, and interactions are all
intentional. Recreate them pixel-close using the codebase's existing UI
library (Tailwind utility classes, design system primitives, whatever the app
uses). If the app already has a `<Dialog>`, `<Table>`, `<Button>`,
`<Checkbox>`, `<Badge>` — use those, do not reinvent.

## Files in `prototype/`

| File | What's in it |
|---|---|
| `Post Suggestions UX.html` | Open in a browser to view the design canvas. |
| `variation-a.jsx` | The full diff modal (`DiffListA`) plus polished states (loading, empty, stale-conflict). The "lean" mode is canonical. |
| `shared.jsx` | Icons, `TriCheck` (tri-state checkbox), `Pill` (chip atom). |
| `mock-data.jsx` | Sample dataset + `classify()` + `PRIORITY_META` + `SKIP_REASON_LABEL`. |
| `tweaks-panel.jsx` | Floating tweaks panel — design-tool only, **do not port**. |

The `lean` mode is the locked-in direction. Modes `tiles` and `tape` exist in
the source but are explicitly **not shipping**.

---

## The screen

One modal. One screen. ~1040×720 max, but fluid — the modal centers itself
in the viewport and the table region scrolls.

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ Header: title + subtitle ……………… [Regenerate] [×]            │  ← 1
├──────────────────────────────────────────────────────────────┤
│ Filter tiles ─ All │ New │ Replace │ Optimal │ Skipped       │  ← 2
├──────────────────────────────────────────────────────────────┤
│ Table:  ☐ │ Post │ Priority │ Member change │ Condition      │  ← 3
│         …rows scroll…                                        │
├──────────────────────────────────────────────────────────────┤
│ Footer: "Apply N changes — X new · Y replacements"  [Cancel] │  ← 4
│                                              [Apply N]       │
└──────────────────────────────────────────────────────────────┘
```

### Section 1 — Header

- Title: **Suggest post assignments** (16 px, 600).
- Subtitle (13 px, slate-500):
  *"{N} posts reviewed · matching against post conditions · expires in {mm:ss}"*.
  The expiry is real — suggestions are only valid for a window (TTL on the
  backend). When it hits zero the modal should auto-close or show a
  regenerate prompt.
- Right side: **Regenerate** (secondary button — outlined, white, slate text)
  and a close icon button.

### Section 2 — Filter tiles

A 5-column grid of buttons (`role="button"`, `aria-pressed`). Clicking a tile
filters the table below; the active tile gets a 2 px ring in its tone color
plus 1 px offset. Tiles are sticky in their bar but the bar doesn't scroll
with the table.

| Tile | Tone | Count source | Hint copy | Notes |
|---|---|---|---|---|
| All posts | slate-900 | total entries | "Everything reviewed" | default selected |
| New assignments | violet-500 | classify === "new" | "Empty positions" | shows `· N selected` inline |
| Replacements | amber-500 | classify === "replace" | "Member would change" | shows `· N selected` inline |
| Already optimal | slate-300 | classify === "same" | "Suggestion = current" | not selectable for apply |
| Skipped | rose-400 | classify === "skipped" | "Cannot fill" | not selectable for apply |

Each tile: ~3 px vertical color bar on left, label uppercase 11 px slate-500,
big number 24 px tabular-nums in tone color, small hint 11 px slate-400.

### Section 3 — Diff table

5 columns: checkbox, post number, priority badge, member change, matched
condition.

**Row densities** — lean mode uses `py-1.5` (compact). Comfy `py-2.5` is in
the source but not shipping.

**Per-row cells:**

- **Checkbox** — tri-state (`TriCheck`). For skipped rows it is rendered
  as visually-off and non-clickable (skipped rows can't be applied).
- **Post** — `#{building_number}` in slate-900, 600 weight, tabular-nums.
- **Priority** — small badge. Tones from `PRIORITY_META` in `mock-data.jsx`:
  - `5` Critical → rose-100 / rose-700
  - `4` High → amber-100 / amber-800
  - `3` Med → sky-100 / sky-700
  - `2` Low → slate-100 / slate-600
  - `1` Min → slate-50 / slate-500
  Text is just the level word, no number.
- **Member change** — depends on classification:
  - **new**: `[empty placeholder]  →  [violet pill: suggested name]`
  - **replace**: `[slate pill, line-through, opacity 70: current]  →  [amber pill: suggested]`
  - **same**: `[slate pill: name]  · stays put` (italic slate-400 hint)
  - **skipped**: italic slate-400 *"No suggestion"*
  Pills max-width truncate with ellipsis. The arrow is a 14 px right-arrow
  icon in slate-400.
- **Matched condition** — green check chip:
  `bg-emerald-50 text-emerald-800 ring-emerald-200`, with the rule's
  `description` string truncated and a small `L{stronghold_level}` suffix.
  When `showAllConditions` (a tweak, see below) is on, additional grey chips
  for non-matched conditions appear below — **not shipping by default**.

**Hover:** `hover:bg-slate-50` on the entire row.
**Selected row:** `bg-violet-50/40` background tint.
**Skipped rows:** no hover, dimmed.

**Skip reasons** — when `classify === "skipped"`, the condition cell shows an
icon + reason instead of a check chip:
- `reserve` → lock icon, "Position is reserved"
- `disabled` → slash-circle icon, "Position disabled"
- other → info icon, "{reason text}"
Reasons live in `SKIP_REASON_LABEL` in `mock-data.jsx`.

### Section 4 — Footer

Sticky. Two zones:
- **Left** (slate-600 13 px): summary sentence
  *"Apply N changes — X new · Y replacements"* with the X colored violet-700
  and Y colored amber-700. When nothing is selected: *"Nothing selected."*
  in slate-400.
- **Right**: `Cancel` (ghost) + `Apply N` (primary slate-900). Apply is
  disabled (40% opacity) when `selectedCount === 0`.

---

## Interactions

### Default selection

On open, **every actionable row is pre-checked** — every row where
`suggested_member_id != null && !matches_current`. The planner's job is to
*deselect* the ones they don't want, not to opt-in from zero. Same/Skipped
rows are never selectable.

### Filter behavior

Filter tiles are mutually exclusive (single-select). Filtering only hides
table rows; it does not change selection state. A row deselected while
filtered to "New" stays deselected when the filter goes back to "All".

### Regenerate

Calls the same suggestion endpoint that opens the modal. While in flight,
swap the table region for a centered spinner + "Generating suggestions…"
(see `StateLoading` in `variation-a.jsx`). Selections are wiped on
regenerate — the new dataset has different position IDs in the result.

### Apply

`POST` the IDs of all checked rows. On success — close modal, refresh the
board. On 409 (some entries are stale because the board changed under the
planner), show the **stale entries banner** (see `StateStaleConflict`):
amber bar across top of the modal listing each stale post + reason, with
buttons:
- *Cancel* — close, no-op
- *Regenerate* — re-fetch suggestions
- *Apply remaining N* — POST again with only the still-valid IDs

The banner replaces the table contents while shown — it's a distinct sub-state.

### Empty preview state

When the suggestion endpoint returns 0 rows (no posts on this siege), show
`StateEmpty` instead of the table: centered icon, "No posts on this siege",
helper copy, and a primary button to "Open settings".

---

## Sort order

Within a filter, rows are sorted by:
1. `priority` descending (Critical first)
2. `building_number` ascending (tiebreaker)

Same/Skipped rows stay in this same sort — they aren't pushed to the bottom.

---

## State

```
{
  status: "loading" | "ready" | "empty" | "stale-conflict",
  data: AssignmentEntry[],   // shape in mock-data.jsx
  filter: "all" | "new" | "replace" | "same" | "skipped",
  checked: Record<position_id, boolean>,
  expiresAt: ISO timestamp,
}
```

`AssignmentEntry` shape (full reference in `mock-data.jsx`):

```ts
type AssignmentEntry = {
  post_id: number;
  position_id: number;             // unique key for selection
  building_number: number;         // displayed as "#{n}"
  priority: 1 | 2 | 3 | 4 | 5;

  current_member_id: number | null;
  current_member_name: string | null;

  suggested_member_id: number | null;
  suggested_member_name: string | null;

  suggested_condition_id: number | null;
  active_conditions: PostCondition[];   // all rules configured on this post

  matches_current: boolean;        // suggested === current
  skip_reason: "reserve" | "disabled" | string | null;
};

type PostCondition = {
  id: number;
  stronghold_level: number;        // displayed as "L{n}" suffix
  description: string;             // free text
};
```

The `classify(entry)` helper in `mock-data.jsx` returns
`"new" | "replace" | "same" | "skipped"`.

---

## Design tokens

All colors are Tailwind v3 names — translate to your token system.

### Surfaces
- Modal bg: `white`
- Modal border: `slate-200`
- Modal shadow: `2xl`
- Tile bar bg: `slate-50`
- Header / footer bg: `white` and `slate-50` respectively
- Row hover: `slate-50`
- Row selected tint: `violet-50/40`

### Text
- Title: `slate-900` 16 px / 600
- Body: `slate-600` 13 px / 400
- Subtle: `slate-500` 13 px / 400
- Hint: `slate-400` 11 px / 400
- Numbers (priority badges, counts): `tabular-nums`

### Outcome tones
| Outcome | Bar | Number text | Soft bg | Active ring |
|---|---|---|---|---|
| All | `slate-900` | `slate-900` | `white` | `slate-900` |
| New | `violet-500` | `violet-700` | `violet-50` | `violet-500` |
| Replace | `amber-500` | `amber-700` | `amber-50` | `amber-500` |
| Optimal | `slate-300` | `slate-600` | `white` | `slate-400` |
| Skipped | `rose-400` | `rose-700` | `rose-50` | `rose-500` |

### Matched condition chip
- bg `emerald-50` · text `emerald-800` · ring `emerald-200`
- check icon: 11 px stroke-2.2

### Spacing
- Modal padding: 24 px horizontal, 16–20 px vertical per section
- Tile padding: 12 px vert × 12 px horiz
- Row vertical padding (lean): 6 px
- Gap between filter tiles: 8 px
- Gap inside member-change cell: 8 px

### Border radius
- Modal: `xl` (12 px)
- Tiles: `lg` (8 px)
- Pills/chips: `md` (6 px)
- Tri-checkbox: `sm` (2 px)

### Typography
- Family: Inter (or whatever the app already uses — do not introduce Inter
  if the codebase has its own font stack).

---

## Accessibility

- Filter tiles: `role="button"`, `aria-pressed={active}`.
- Tri-checkbox: should be a real `<input type="checkbox">` with proper
  `aria-checked="mixed"` for the indeterminate state when ported. The HTML
  prototype fakes it with a styled `<button>` — don't ship that.
- Modal: trap focus, ESC closes, focus returns to invoking trigger on close.
- Apply / Cancel are real buttons. Apply gets an `aria-disabled` when no
  selection.

---

## Out of scope / not shipping

- The Tweaks panel (`tweaks-panel.jsx`) — design-tool only.
- The `tiles` and `tape` modes in `variation-a.jsx` — kept in source for
  reference but lean is canonical.
- The `showAllConditions` tweak (showing non-matched conditions as grey
  chips). Off by default; only the matched condition ships.
- The priority stripe (vertical color bar on the leftmost cell of each row).
  Off in lean mode.

---

## Implementation order suggestion

1. Bare table with mock data — get the shape right.
2. Tri-state checkbox + selection state.
3. Filter tiles wired up.
4. Polish: pills, condition chips, priority badges.
5. Footer summary + Apply wiring.
6. Loading, empty, stale-conflict sub-states.
7. Real endpoint integration + expiry timer.
