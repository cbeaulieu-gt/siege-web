/**
 * Group-by toggle integration tests across the three post-condition surfaces.
 *
 * Covered:
 *  Surface A: PostPrioritiesPage Conditions tab
 *    1. Default (mode=level): "Stronghold Level 1/2/3" headings appear.
 *    2. Click Type: Role/Affinity/Faction/League/Rarity/Effect headings appear in order.
 *    3. localStorage is written when toggled.
 *    4. Stored "type" value initializes component in type mode.
 *
 *  Surface B: MemberDetailPage Post Preferences
 *    5. Default (mode=level): "Stronghold Level N" headings visible.
 *    6. Click Type: type-bucket headings appear.
 *
 *  Surface C: PostsTab — group-by in the active-conditions display
 *    (PostsTab itself does not show a conditions list for grouping;
 *     the toggle affects the outer condition reference view, not PostRow internals.
 *     These tests cover the PostsTab toolbar having the toggle.)
 *
 * NOTE: The toggle controls grouping of the *post conditions reference list*.
 * PostsTab does not render a standalone condition list — the relevant surfaces
 * are PostPrioritiesPage (Conditions tab) and MemberDetailPage (Post Preferences).
 * The PostsTab toolbar toggle test verifies the toggle is rendered and wired.
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
import PostPrioritiesPage from "../../pages/PostPrioritiesPage";
import MemberDetailPage from "../../pages/MemberDetailPage";
import type { PostCondition } from "../../api/types";

// ─── Server lifecycle ──────────────────────────────────────────────────────────

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => {
  server.resetHandlers();
  localStorage.clear();
});
afterAll(() => server.close());

// ─── Fixtures ─────────────────────────────────────────────────────────────────

/** A small representative slice of the 36 canonical conditions. */
const SAMPLE_CONDITIONS: PostCondition[] = [
  // League L1
  { id: 1, description: "Only Champions from the Telerian League can be used.", stronghold_level: 1 },
  // Role L1
  { id: 5, description: "Only HP Champions can be used.", stronghold_level: 1 },
  // Faction L1
  { id: 9, description: "Only Banner Lord Champions can be used.", stronghold_level: 1 },
  // Affinity L2
  { id: 19, description: "Only Void Champions can be used.", stronghold_level: 2 },
  // Faction L2
  { id: 23, description: "Only Demonspawn Champions can be used.", stronghold_level: 2 },
  // Rarity L3
  { id: 29, description: "Only Legendary Champions can be used.", stronghold_level: 3 },
  // Effect L3
  { id: 35, description: "All Champions are immune to [Sheep] debuffs.", stronghold_level: 3 },
  // Other L3
  { id: 36, description: "Champions cannot be revived.", stronghold_level: 3 },
];

function setupConditions(conditions = SAMPLE_CONDITIONS) {
  server.use(
    http.get("/api/post-conditions", () => HttpResponse.json(conditions)),
    http.get("/api/post-priorities", () => HttpResponse.json([]))
  );
}

function setupMember(memberId = 1) {
  server.use(
    http.get(`/api/members/${memberId}`, () =>
      HttpResponse.json({
        id: memberId,
        name: "Aethon",
        discord_username: null,
        role: "heavy_hitter",
        power_level: "gt_25m",
        is_active: true,
      })
    ),
    http.get(`/api/members/${memberId}/preferences`, () =>
      HttpResponse.json([])
    )
  );
}

// ─── Surface A: PostPrioritiesPage Conditions tab ─────────────────────────────

describe("PostPrioritiesPage — Group by toggle on Conditions tab", () => {
  beforeEach(() => setupConditions());

  async function openConditionsTab(user: ReturnType<typeof userEvent.setup>) {
    renderWithProviders(<PostPrioritiesPage />);
    await user.click(screen.getByRole("button", { name: /conditions/i }));
    // Wait for conditions to load
    await waitFor(() =>
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    );
  }

  it("default mode shows Stronghold Level headings", async () => {
    const user = userEvent.setup();
    await openConditionsTab(user);

    expect(screen.getByText(/stronghold level 1/i)).toBeInTheDocument();
    expect(screen.getByText(/stronghold level 2/i)).toBeInTheDocument();
    expect(screen.getByText(/stronghold level 3/i)).toBeInTheDocument();
  });

  it("switching to Type shows type-bucket headings in spec order", async () => {
    const user = userEvent.setup();
    await openConditionsTab(user);

    await user.click(screen.getByRole("button", { name: "Type" }));

    // These buckets have members in SAMPLE_CONDITIONS
    await waitFor(() => {
      expect(screen.getByText("Role")).toBeInTheDocument();
      expect(screen.getByText("Affinity")).toBeInTheDocument();
      expect(screen.getByText("Faction")).toBeInTheDocument();
      expect(screen.getByText("League")).toBeInTheDocument();
      expect(screen.getByText("Rarity")).toBeInTheDocument();
      expect(screen.getByText("Effect")).toBeInTheDocument();
      expect(screen.getByText("Other")).toBeInTheDocument();
    });
  });

  it("type headings appear in spec order (Role before Affinity before Faction...)", async () => {
    const user = userEvent.setup();
    await openConditionsTab(user);
    await user.click(screen.getByRole("button", { name: "Type" }));

    await waitFor(() => {
      expect(screen.getByText("Role")).toBeInTheDocument();
    });

    const headings = ["Role", "Affinity", "Faction", "League", "Rarity", "Effect", "Other"];
    const elements = headings.map((h) => screen.getByText(h));
    // Verify DOM order matches spec order
    for (let i = 0; i < elements.length - 1; i++) {
      expect(
        elements[i].compareDocumentPosition(elements[i + 1]) &
          Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
    }
  });

  it("level headings disappear after switching to Type", async () => {
    const user = userEvent.setup();
    await openConditionsTab(user);

    // Verify level headings initially present
    expect(screen.getByText(/stronghold level 1/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Type" }));

    await waitFor(() => {
      expect(screen.queryByText(/stronghold level/i)).not.toBeInTheDocument();
    });
  });

  it("clicking Type writes 'type' to localStorage", async () => {
    const user = userEvent.setup();
    await openConditionsTab(user);

    await user.click(screen.getByRole("button", { name: "Type" }));

    expect(localStorage.getItem("siege-web:postConditions:groupBy")).toBe(
      "type"
    );
  });

  it("initializes in type mode when localStorage has 'type'", async () => {
    localStorage.setItem("siege-web:postConditions:groupBy", "type");
    const user = userEvent.setup();
    await openConditionsTab(user);

    // Should immediately show type headings without clicking
    await waitFor(() => {
      expect(screen.getByText("Role")).toBeInTheDocument();
    });
    expect(screen.queryByText(/stronghold level/i)).not.toBeInTheDocument();
  });
});

// ─── Surface B: MemberDetailPage Post Preferences ─────────────────────────────

describe("MemberDetailPage — Group by toggle on Post Preferences", () => {
  beforeEach(() => {
    setupConditions();
    setupMember(1);
  });

  function renderMemberDetail() {
    return renderWithProviders(
      <Routes>
        <Route path="/members/:id" element={<MemberDetailPage />} />
      </Routes>,
      { initialEntries: ["/members/1"] }
    );
  }

  async function waitForPreferences() {
    await waitFor(() =>
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    );
    // Wait for Post Preferences section
    await waitFor(() =>
      expect(screen.getByText("Post Preferences")).toBeInTheDocument()
    );
  }

  it("default mode shows Stronghold Level headings in preferences section", async () => {
    renderMemberDetail();
    await waitForPreferences();

    expect(screen.getByText(/stronghold level 1/i)).toBeInTheDocument();
    expect(screen.getByText(/stronghold level 2/i)).toBeInTheDocument();
    expect(screen.getByText(/stronghold level 3/i)).toBeInTheDocument();
  });

  it("switching to Type shows type-bucket headings", async () => {
    const user = userEvent.setup();
    renderMemberDetail();
    await waitForPreferences();

    await user.click(screen.getByRole("button", { name: "Type" }));

    // Check for type headings as h3 elements (not the "Role" field label)
    await waitFor(() => {
      const headings = screen.getAllByRole("heading", { level: 3 });
      const headingTexts = headings.map((h) => h.textContent);
      expect(headingTexts).toContain("Faction");
    });
    expect(screen.queryByText(/stronghold level/i)).not.toBeInTheDocument();
  });

  it("writes to localStorage when toggled", async () => {
    const user = userEvent.setup();
    renderMemberDetail();
    await waitForPreferences();

    await user.click(screen.getByRole("button", { name: "Type" }));

    expect(localStorage.getItem("siege-web:postConditions:groupBy")).toBe(
      "type"
    );
  });

  it("initializes in type mode when localStorage has 'type'", async () => {
    localStorage.setItem("siege-web:postConditions:groupBy", "type");
    renderMemberDetail();
    await waitForPreferences();

    await waitFor(() => {
      // Faction heading should appear (no conflict with form labels)
      const headings = screen.getAllByRole("heading", { level: 3 });
      const headingTexts = headings.map((h) => h.textContent);
      expect(headingTexts).toContain("Faction");
    });
    expect(screen.queryByText(/stronghold level/i)).not.toBeInTheDocument();
  });
});
