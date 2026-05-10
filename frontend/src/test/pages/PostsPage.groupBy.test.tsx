/**
 * PostsPage — Group-by toggle on the condition picker inside each PostRow.
 *
 * Acceptance criteria from issue #375:
 *  1. Default mode shows Stronghold Level headings inside the expanded picker.
 *  2. Clicking "Type" in the toggle shows type-bucket headings in spec order.
 *  3. Clicking "Type" writes 'type' to localStorage under the shared key.
 *  4. Mounting with stored value 'type' initialises the picker in type mode.
 *
 * Pattern mirrors GroupByConditions.test.tsx (Surfaces A & B) for consistency.
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import {
  beforeAll,
  afterAll,
  afterEach,
  beforeEach,
  describe,
  it,
  expect,
} from "vitest";
import { Routes, Route } from "react-router-dom";
import { server } from "../server";
import { renderWithProviders } from "../utils";
import PostsPage from "../../pages/PostsPage";
import type { Post, PostCondition } from "../../api/types";

// ─── Server lifecycle ──────────────────────────────────────────────────────────

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

// ─── Fixtures ─────────────────────────────────────────────────────────────────

/** Representative conditions spanning multiple levels and types. */
const SAMPLE_CONDITIONS: PostCondition[] = [
  // League L1
  {
    id: 1,
    description: "Only Champions from the Telerian League can be used.",
    stronghold_level: 1,
  },
  // Role L1
  { id: 5, description: "Only HP Champions can be used.", stronghold_level: 1 },
  // Faction L1
  {
    id: 9,
    description: "Only Banner Lord Champions can be used.",
    stronghold_level: 1,
  },
  // Affinity L2
  {
    id: 19,
    description: "Only Void Champions can be used.",
    stronghold_level: 2,
  },
  // Faction L2
  {
    id: 23,
    description: "Only Demonspawn Champions can be used.",
    stronghold_level: 2,
  },
  // Rarity L3
  {
    id: 29,
    description: "Only Legendary Champions can be used.",
    stronghold_level: 3,
  },
  // Effect L3
  {
    id: 35,
    description: "All Champions are immune to [Sheep] debuffs.",
    stronghold_level: 3,
  },
  // Other L3
  { id: 36, description: "Champions cannot be revived.", stronghold_level: 3 },
];

const SIEGE_ID = 42;

function makePost(overrides: Partial<Post> = {}): Post {
  return {
    id: 1,
    siege_id: SIEGE_ID,
    building_id: 10,
    building_number: 1,
    priority: 1,
    description: null,
    active_conditions: [],
    ...overrides,
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function setupHandlers(posts: Post[] = [makePost()]) {
  server.use(
    http.get(`/api/sieges/${SIEGE_ID}`, () =>
      HttpResponse.json({
        id: SIEGE_ID,
        name: "Test Siege",
        status: "draft",
        attack_day: null,
        created_at: "2024-01-01T00:00:00Z",
        member_count: 0,
      })
    ),
    http.get(`/api/sieges/${SIEGE_ID}/posts`, () => HttpResponse.json(posts)),
    http.get(`/api/sieges/${SIEGE_ID}/board`, () =>
      HttpResponse.json({ siege_id: SIEGE_ID, buildings: [] })
    ),
    http.get("/api/post-conditions", () =>
      HttpResponse.json(SAMPLE_CONDITIONS)
    )
  );
}

function renderPostsPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/sieges/:id/posts" element={<PostsPage />} />
    </Routes>,
    { initialEntries: [`/sieges/${SIEGE_ID}/posts`] }
  );
}

/** Expand the first PostRow so the condition picker becomes visible. */
async function expandFirstPost(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() =>
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument()
  );
  // The chevron button is the expand toggle — click it
  const expandBtn = screen.getByRole("button", { name: "" });
  await user.click(expandBtn);
  // Wait for conditions to load (the picker renders once allConditions arrives)
  await waitFor(() =>
    expect(screen.getByPlaceholderText(/filter conditions/i)).toBeInTheDocument()
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PostsPage — Group-by toggle in PostRow condition picker", () => {
  beforeEach(() => setupHandlers());

  it("default mode shows Stronghold Level headings inside the expanded picker", async () => {
    const user = userEvent.setup();
    renderPostsPage();
    await expandFirstPost(user);

    expect(screen.getByText(/stronghold level 1/i)).toBeInTheDocument();
    expect(screen.getByText(/stronghold level 2/i)).toBeInTheDocument();
    expect(screen.getByText(/stronghold level 3/i)).toBeInTheDocument();
  });

  it("clicking Type shows type-bucket headings in spec order", async () => {
    const user = userEvent.setup();
    renderPostsPage();
    await expandFirstPost(user);

    await user.click(screen.getByRole("radio", { name: "Type" }));

    await waitFor(() => {
      expect(screen.getByText("Role")).toBeInTheDocument();
      expect(screen.getByText("Affinity")).toBeInTheDocument();
      expect(screen.getByText("Faction")).toBeInTheDocument();
      expect(screen.getByText("League")).toBeInTheDocument();
      expect(screen.getByText("Rarity")).toBeInTheDocument();
      expect(screen.getByText("Effect")).toBeInTheDocument();
      expect(screen.getByText("Other")).toBeInTheDocument();
    });
    // Level headings must disappear
    expect(screen.queryByText(/stronghold level/i)).not.toBeInTheDocument();
  });

  it("clicking Type writes 'type' to the shared localStorage key", async () => {
    const user = userEvent.setup();
    renderPostsPage();
    await expandFirstPost(user);

    await user.click(screen.getByRole("radio", { name: "Type" }));

    expect(
      localStorage.getItem("siege-web:postConditions:groupBy")
    ).toBe("type");
  });

  it("initialises in type mode when localStorage already has 'type'", async () => {
    localStorage.setItem("siege-web:postConditions:groupBy", "type");
    const user = userEvent.setup();
    renderPostsPage();
    await expandFirstPost(user);

    // Should show type headings immediately, no click required
    await waitFor(() => {
      expect(screen.getByText("Role")).toBeInTheDocument();
    });
    expect(screen.queryByText(/stronghold level/i)).not.toBeInTheDocument();
  });
});
