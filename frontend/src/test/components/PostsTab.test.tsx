/**
 * PostsTab matched condition display tests
 *
 * These tests render BoardPage and switch to the Posts tab — matching the
 * integration-test pattern used in BoardPage.test.tsx — because PostsTab
 * requires siege + board data that flows from its parent.
 *
 * Covered cases:
 *  1. Condition pill appears when matched_condition_id resolves to an active condition
 *  2. No pill when matched_condition_id is null
 *  3. No pill when matched_condition_id doesn't match any active condition
 *  4. No pill for reserve slots (is_reserve=true)
 *
 * Inline duplicate-condition indicator (issue #196):
 *  5. Warning icon + "Post N" shown on radio when member+condition already assigned on a different post
 *  6. No warning icon when member+condition pair has no entry in duplicateMap
 *  7. No warning icon when duplicateMap entry points to the same post (self-reference)
 *  8. Post-click confirmation dialog still appears for duplicate cases (additive, not replacement)
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeAll, afterAll, afterEach, describe, it, expect } from "vitest";
import { Routes, Route } from "react-router-dom";
import { server } from "../server";
import { renderWithProviders } from "../utils";
import BoardPage from "../../pages/BoardPage";
import type {
  BoardResponse,
  PositionResponse,
  SiegeMember,
  Siege,
  Post,
} from "../../api/types";

// ─── Server lifecycle ──────────────────────────────────────────────────────────

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ─── Fixture factories ─────────────────────────────────────────────────────────

function makePosition(
  overrides: Partial<PositionResponse> = {}
): PositionResponse {
  return {
    id: 1,
    position_number: 1,
    member_id: null,
    member_name: null,
    is_reserve: false,
    is_disabled: false,
    matched_condition_id: null,
    ...overrides,
  };
}

/**
 * Make a board containing a single post building (building_type='post').
 * PostsTab only renders rows for buildings with building_type='post'.
 */
function makePostBoard(positions: PositionResponse[] = []): BoardResponse {
  return {
    siege_id: 42,
    buildings: [
      {
        id: 20,
        building_type: "post",
        building_number: 1,
        level: 3,
        is_broken: false,
        groups: [
          {
            id: 200,
            group_number: 1,
            slot_count: Math.max(positions.length, 1),
            positions: positions.length > 0 ? positions : [makePosition()],
          },
        ],
      },
    ],
  };
}

function makeSiege(overrides: Partial<Siege> = {}): Siege {
  return {
    id: 42,
    date: "2026-03-22",
    status: "active",
    defense_scroll_count: 0,
    computed_scroll_count: 0,
    created_at: "2026-03-19T00:00:00Z",
    updated_at: "2026-03-19T00:00:00Z",
    ...overrides,
  };
}

function makeSiegeMember(overrides: Partial<SiegeMember> = {}): SiegeMember {
  return {
    siege_id: 42,
    member_id: 1,
    member_name: "Aethon",
    member_role: "heavy_hitter",
    member_power_level: "gt_25m",
    attack_day: 1,
    has_reserve_set: false,
    attack_day_override: false,
    ...overrides,
  };
}

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: 1,
    siege_id: 42,
    building_id: 20,
    building_number: 1,
    priority: 1,
    description: null,
    active_conditions: [],
    ...overrides,
  };
}

/**
 * Register the MSW handlers that BoardPage and PostsTab always query.
 * PostsTab additionally fetches /api/sieges/42/posts and
 * /api/sieges/42/members/preferences.
 */
function setupHandlers(
  board: BoardResponse,
  siege: Siege = makeSiege(),
  members: SiegeMember[] = [],
  posts: Post[] = []
) {
  server.use(
    http.get("/api/sieges/42/board", () => HttpResponse.json(board)),
    http.get("/api/sieges/42", () => HttpResponse.json(siege)),
    http.get("/api/sieges/42/members", () => HttpResponse.json(members)),
    http.get("/api/post-priorities", () => HttpResponse.json([])),
    http.get("/api/sieges/42/posts", () => HttpResponse.json(posts)),
    http.get("/api/sieges/42/members/preferences", () => HttpResponse.json([]))
  );
}

function renderBoard(initialPath = "/sieges/42/board") {
  return renderWithProviders(
    <Routes>
      <Route path="/sieges/:id/board" element={<BoardPage />} />
    </Routes>,
    { initialEntries: [initialPath] }
  );
}

/** Wait for the board to load and then click the Posts tab button. */
async function navigateToPostsTab(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() =>
    expect(screen.queryByText(/loading board/i)).not.toBeInTheDocument()
  );
  await user.click(screen.getByRole("button", { name: /posts/i }));
  // Wait for PostsTab to finish loading its own queries
  await waitFor(() =>
    expect(screen.queryByText(/loading posts/i)).not.toBeInTheDocument()
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PostsTab — matched condition display", () => {
  it("shows condition pill in collapsed row when matched_condition_id matches an active condition", async () => {
    const user = userEvent.setup();

    const position = makePosition({
      id: 10,
      member_id: 1,
      member_name: "Aethon",
      matched_condition_id: 5,
    });
    const post = makePost({
      active_conditions: [
        { id: 5, description: "Condition B", stronghold_level: 3 },
      ],
    });

    setupHandlers(
      makePostBoard([position]),
      makeSiege(),
      [makeSiegeMember()],
      [post]
    );
    renderBoard();

    await navigateToPostsTab(user);

    // The condition pill is rendered inline in the collapsed row
    expect(screen.getByText("Condition B")).toBeInTheDocument();
  });

  it("does not show condition pill when matched_condition_id is null", async () => {
    const user = userEvent.setup();

    const position = makePosition({
      id: 11,
      member_id: 1,
      member_name: "Aethon",
      matched_condition_id: null,
    });
    const post = makePost({
      active_conditions: [
        { id: 5, description: "Condition B", stronghold_level: 3 },
      ],
    });

    setupHandlers(
      makePostBoard([position]),
      makeSiege(),
      [makeSiegeMember()],
      [post]
    );
    renderBoard();

    await navigateToPostsTab(user);

    // No condition pill should appear
    expect(screen.queryByText("Condition B")).not.toBeInTheDocument();
  });

  it("does not show condition pill when matched_condition_id does not match any active condition", async () => {
    const user = userEvent.setup();

    const position = makePosition({
      id: 12,
      member_id: 1,
      member_name: "Aethon",
      matched_condition_id: 99, // id 99 is not in active_conditions
    });
    const post = makePost({
      active_conditions: [
        { id: 5, description: "Condition B", stronghold_level: 3 },
      ],
    });

    setupHandlers(
      makePostBoard([position]),
      makeSiege(),
      [makeSiegeMember()],
      [post]
    );
    renderBoard();

    await navigateToPostsTab(user);

    // id 99 has no matching condition — no pill should render
    expect(screen.queryByText("Condition B")).not.toBeInTheDocument();
  });

  it("does not show condition pill for a reserve slot even when matched_condition_id is set", async () => {
    const user = userEvent.setup();

    const position = makePosition({
      id: 13,
      is_reserve: true,
      matched_condition_id: 5,
    });
    const post = makePost({
      active_conditions: [
        { id: 5, description: "Condition B", stronghold_level: 3 },
      ],
    });

    setupHandlers(
      makePostBoard([position]),
      makeSiege(),
      [makeSiegeMember()],
      [post]
    );
    renderBoard();

    await navigateToPostsTab(user);

    // Reserve slots show "RESERVE" but never the condition pill
    expect(screen.getByText("RESERVE")).toBeInTheDocument();
    expect(screen.queryByText("Condition B")).not.toBeInTheDocument();
  });
});

// ─── Inline duplicate-condition indicator (issue #196) ─────────────────────────

/**
 * Board fixture with TWO post buildings so one can act as the "other post"
 * where the member+condition conflict lives.
 *
 * - Post 1 (building_number=1): the post the user is looking at (unassigned)
 * - Post 2 (building_number=2): already has member 1 assigned with condition 5
 */
function makeTwoPostBoard(post2Position: Partial<PositionResponse> = {}): BoardResponse {
  return {
    siege_id: 42,
    buildings: [
      {
        id: 20,
        building_type: "post",
        building_number: 1,
        level: 3,
        is_broken: false,
        groups: [
          {
            id: 200,
            group_number: 1,
            slot_count: 1,
            positions: [makePosition({ id: 1 })],
          },
        ],
      },
      {
        id: 21,
        building_type: "post",
        building_number: 2,
        level: 3,
        is_broken: false,
        groups: [
          {
            id: 201,
            group_number: 1,
            slot_count: 1,
            positions: [
              makePosition({
                id: 2,
                member_id: 1,
                member_name: "Aethon",
                matched_condition_id: 5,
                ...post2Position,
              }),
            ],
          },
        ],
      },
    ],
  };
}

describe("PostsTab — inline duplicate-condition indicator (#196)", () => {
  it("shows warning icon and post number on radio when member+condition already assigned on a different post", async () => {
    const user = userEvent.setup();

    // Post 2 already has member 1 with condition 5.
    // Post 1 is unassigned; member 1 has condition 5 as a preference.
    const board = makeTwoPostBoard();
    const post1 = makePost({
      id: 1,
      building_number: 1,
      active_conditions: [
        { id: 5, description: "Great Fortification", stronghold_level: 3 },
      ],
    });
    const post2 = makePost({
      id: 2,
      building_id: 21,
      building_number: 2,
      active_conditions: [
        { id: 5, description: "Great Fortification", stronghold_level: 3 },
      ],
    });
    const member = makeSiegeMember({ member_id: 1, member_name: "Aethon" });

    server.use(
      http.get("/api/sieges/42/board", () => HttpResponse.json(board)),
      http.get("/api/sieges/42", () => HttpResponse.json(makeSiege())),
      http.get("/api/sieges/42/members", () => HttpResponse.json([member])),
      http.get("/api/post-priorities", () => HttpResponse.json([])),
      http.get("/api/sieges/42/posts", () => HttpResponse.json([post1, post2])),
      http.get("/api/sieges/42/members/preferences", () =>
        HttpResponse.json([
          { member_id: 1, preferences: [{ id: 5, description: "Great Fortification", stronghold_level: 3 }] },
        ])
      )
    );
    renderBoard();

    await navigateToPostsTab(user);

    // Expand Post 1
    await user.click(screen.getByRole("button", { name: /post 1/i }));

    // The inline duplicate indicator should appear next to the radio for "Great Fortification"
    // showing "Post 2" as the conflicting post — inside a <label> element on the radio button.
    await waitFor(() => {
      const postRefs = screen.getAllByText("Post 2");
      // At least one occurrence must be inside a <label> (the inline indicator on the radio)
      expect(postRefs.some((el) => el.closest("label") !== null)).toBe(true);
    });
  });

  it("does not show warning icon when member+condition pair has no duplicate entry", async () => {
    const user = userEvent.setup();

    // Post 2 has member 1 with condition 5.
    // Post 1 has condition 7 (different) — no conflict for member 1 + condition 7.
    const board = makeTwoPostBoard();
    const post1 = makePost({
      id: 1,
      building_number: 1,
      active_conditions: [
        { id: 7, description: "Stone Skin", stronghold_level: 3 },
      ],
    });
    const post2 = makePost({
      id: 2,
      building_id: 21,
      building_number: 2,
      active_conditions: [
        { id: 5, description: "Great Fortification", stronghold_level: 3 },
      ],
    });
    const member = makeSiegeMember({ member_id: 1, member_name: "Aethon" });

    server.use(
      http.get("/api/sieges/42/board", () => HttpResponse.json(board)),
      http.get("/api/sieges/42", () => HttpResponse.json(makeSiege())),
      http.get("/api/sieges/42/members", () => HttpResponse.json([member])),
      http.get("/api/post-priorities", () => HttpResponse.json([])),
      http.get("/api/sieges/42/posts", () => HttpResponse.json([post1, post2])),
      http.get("/api/sieges/42/members/preferences", () =>
        HttpResponse.json([
          { member_id: 1, preferences: [{ id: 7, description: "Stone Skin", stronghold_level: 3 }] },
        ])
      )
    );
    renderBoard();

    await navigateToPostsTab(user);

    // Expand Post 1
    await user.click(screen.getByRole("button", { name: /post 1/i }));

    // Radio label with "Stone Skin" should appear (the one inside a <label> element)
    await waitFor(() => {
      const labels = screen.getAllByText("Stone Skin");
      expect(labels.some((el) => el.closest("label") !== null)).toBe(true);
    });
    // No "Post N" warning text should be present inside a label (inline indicator)
    expect(screen.queryAllByText(/^Post \d+$/).filter((el) => el.closest("label") !== null)).toHaveLength(0);
  });

  it("does not show warning icon when duplicateMap entry matches the same post (self-reference)", async () => {
    const user = userEvent.setup();

    // Post 1 already has member 1 with condition 5 assigned (same post).
    // buildDuplicateConditionMap records member_1_condition_5 → building_number=1.
    // When viewing Post 1's radio for "Great Fortification", the building number
    // matches → no duplicate, no indicator.
    const board: BoardResponse = {
      siege_id: 42,
      buildings: [
        {
          id: 20,
          building_type: "post",
          building_number: 1,
          level: 3,
          is_broken: false,
          groups: [
            {
              id: 200,
              group_number: 1,
              slot_count: 1,
              positions: [
                makePosition({
                  id: 1,
                  member_id: 1,
                  member_name: "Aethon",
                  matched_condition_id: 5,
                }),
              ],
            },
          ],
        },
      ],
    };
    const post1 = makePost({
      id: 1,
      building_number: 1,
      active_conditions: [
        { id: 5, description: "Great Fortification", stronghold_level: 3 },
      ],
    });
    const member = makeSiegeMember({ member_id: 1, member_name: "Aethon" });

    server.use(
      http.get("/api/sieges/42/board", () => HttpResponse.json(board)),
      http.get("/api/sieges/42", () => HttpResponse.json(makeSiege())),
      http.get("/api/sieges/42/members", () => HttpResponse.json([member])),
      http.get("/api/post-priorities", () => HttpResponse.json([])),
      http.get("/api/sieges/42/posts", () => HttpResponse.json([post1])),
      http.get("/api/sieges/42/members/preferences", () =>
        HttpResponse.json([
          { member_id: 1, preferences: [{ id: 5, description: "Great Fortification", stronghold_level: 3 }] },
        ])
      )
    );
    renderBoard();

    await navigateToPostsTab(user);

    // Expand Post 1
    await user.click(screen.getByRole("button", { name: /post 1/i }));

    // Radio label with "Great Fortification" should appear (inside a <label> element)
    await waitFor(() => {
      const labels = screen.getAllByText("Great Fortification");
      expect(labels.some((el) => el.closest("label") !== null)).toBe(true);
    });
    // No inline "Post N" warning inside a label (self-reference should not trigger indicator)
    expect(screen.queryAllByText(/^Post \d+$/).filter((el) => el.closest("label") !== null)).toHaveLength(0);
  });

  it("post-click amber confirmation dialog still appears when Assign is clicked for a duplicate (additive behavior)", async () => {
    const user = userEvent.setup();

    // Same two-post setup as test 1: member 1 + condition 5 on post 2.
    // When user clicks Assign on post 1, the existing handleAssignClick dialog fires.
    const board = makeTwoPostBoard();
    const post1 = makePost({
      id: 1,
      building_number: 1,
      active_conditions: [
        { id: 5, description: "Great Fortification", stronghold_level: 3 },
      ],
    });
    const post2 = makePost({
      id: 2,
      building_id: 21,
      building_number: 2,
      active_conditions: [
        { id: 5, description: "Great Fortification", stronghold_level: 3 },
      ],
    });
    const member = makeSiegeMember({ member_id: 1, member_name: "Aethon" });

    server.use(
      http.get("/api/sieges/42/board", () => HttpResponse.json(board)),
      http.get("/api/sieges/42", () => HttpResponse.json(makeSiege())),
      http.get("/api/sieges/42/members", () => HttpResponse.json([member])),
      http.get("/api/post-priorities", () => HttpResponse.json([])),
      http.get("/api/sieges/42/posts", () => HttpResponse.json([post1, post2])),
      http.get("/api/sieges/42/members/preferences", () =>
        HttpResponse.json([
          { member_id: 1, preferences: [{ id: 5, description: "Great Fortification", stronghold_level: 3 }] },
        ])
      )
    );
    renderBoard();

    await navigateToPostsTab(user);

    // Expand Post 1
    await user.click(screen.getByRole("button", { name: /post 1/i }));

    // Wait for the Assign button to appear
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /^assign$/i })).toBeInTheDocument();
    });

    // Click Assign — should trigger the existing confirmation flow
    await user.click(screen.getByRole("button", { name: /^assign$/i }));

    // The "Confirm anyway" button from the amber confirmation dialog should appear
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /confirm anyway/i })
      ).toBeInTheDocument();
    });
  });
});
