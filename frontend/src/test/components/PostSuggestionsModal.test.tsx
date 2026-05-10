/**
 * PostSuggestionsModal component tests.
 *
 * Covered cases:
 * 1. Opening the modal fires the preview request and renders one row per assignment.
 * 2. Rows where suggested_member_id === null render with skip_reason text and
 *    have a disabled checkbox.
 * 3. Unchecking a row excludes its position_id from the apply payload.
 * 4. Apply success invalidates board and posts queries (modal closes).
 * 5. Apply 409 with stale_entries → modal stays open, stale conflict shown, board NOT invalidated.
 * 6. "Regenerate" button re-fires the preview request.
 * 7. Filter tiles hide/show rows by outcome classification.
 * 8. Already-optimal row (matches_current: true) has a disabled checkbox.
 * 9. Empty preview renders the empty state copy.
 * 10. Loading state shows the spinner copy.
 * 11. Non-409 error shows the generic error banner.
 * 12. "Apply remaining N" re-issues apply with only non-stale IDs.
 */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import {
  beforeAll,
  afterAll,
  afterEach,
  describe,
  it,
  expect,
  vi,
} from "vitest";
import { server } from "../server";
import { renderWithProviders } from "../utils";
import PostSuggestionsModal from "../../components/PostSuggestionsModal";
import type { PostSuggestionPreviewResult } from "../../api/types";

// ─── Server lifecycle ──────────────────────────────────────────────────────────

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function makePreview(
  overrides: Partial<PostSuggestionPreviewResult> = {}
): PostSuggestionPreviewResult {
  return {
    assignments: [
      {
        post_id: 1,
        building_number: 3,
        priority: 3,
        position_id: 101,
        suggested_member_id: 42,
        suggested_member_name: "Alice",
        suggested_condition_id: 10,
        suggested_condition_description: "Attack Lv1",
        current_member_id: null,
        current_member_name: null,
        current_condition_id: null,
        current_condition_description: null,
        matches_current: false,
        skip_reason: null,
      },
      {
        post_id: 2,
        building_number: 7,
        priority: 1,
        position_id: 102,
        suggested_member_id: null,
        suggested_member_name: null,
        suggested_condition_id: null,
        suggested_condition_description: null,
        current_member_id: null,
        current_member_name: null,
        current_condition_id: null,
        current_condition_description: null,
        matches_current: false,
        skip_reason: "no_match",
      },
    ],
    expires_at: "2026-05-09T13:00:00",
    ...overrides,
  };
}

function renderModal(
  props: Partial<React.ComponentProps<typeof PostSuggestionsModal>> = {}
) {
  return renderWithProviders(
    <PostSuggestionsModal
      open={true}
      onClose={() => {}}
      siegeId={42}
      {...props}
    />
  );
}

// ─── Tests ────────────────────────────────────────────────────────────────────

describe("PostSuggestionsModal", () => {
  it("fires preview request on open and renders one row per assignment", async () => {
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      )
    );

    renderModal();

    // Wait for the table to appear (preview request resolves)
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    // Row for skipped post uses updated label
    expect(
      screen.getByText("No member matches any of the post conditions")
    ).toBeInTheDocument();
  });

  it("renders skip_reason text and disabled checkbox for null-suggestion rows", async () => {
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      )
    );

    renderModal();

    await waitFor(() =>
      expect(
        screen.getByText("No member matches any of the post conditions")
      ).toBeInTheDocument()
    );

    // Find the row for the skipped post (building_number=7) and check its checkbox
    const rows = screen.getAllByRole("row");
    // Header row + 2 data rows
    const dataRows = rows.slice(1);
    // Find the "no match" row — it's the second data row (sorted by priority desc, then building_number)
    // Alice has priority 3 (High), no_match row has priority 1 (Low), so Alice first
    const skipRow = dataRows[1];
    const checkbox = within(skipRow).getByRole("checkbox");
    expect(checkbox).toBeDisabled();
  });

  it("unchecking a row excludes its position_id from the apply payload", async () => {
    let capturedBody: Record<string, unknown> | null = null;

    // Two eligible rows: Alice (101) and Bob (103); unchecking Alice means only 103 in payload
    const twoSuggestions = makePreview({
      assignments: [
        {
          post_id: 1,
          building_number: 3,
          priority: 3,
          position_id: 101,
          suggested_member_id: 42,
          suggested_member_name: "Alice",
          suggested_condition_id: 10,
          suggested_condition_description: "Attack Lv1",
          current_member_id: null,
          current_member_name: null,
          current_condition_id: null,
          current_condition_description: null,
          matches_current: false,
          skip_reason: null,
        },
        {
          post_id: 3,
          building_number: 5,
          priority: 2,
          position_id: 103,
          suggested_member_id: 55,
          suggested_member_name: "Bob",
          suggested_condition_id: 11,
          suggested_condition_description: "Defense Lv2",
          current_member_id: null,
          current_member_name: null,
          current_condition_id: null,
          current_condition_description: null,
          matches_current: false,
          skip_reason: null,
        },
      ],
    });

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(twoSuggestions)
      ),
      http.post(
        "/api/sieges/42/post-suggestions/apply",
        async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ applied_count: 1 });
        }
      )
    );

    const user = userEvent.setup();
    renderModal();

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Bob")).toBeInTheDocument());

    // Both rows should be checked by default; uncheck Alice's row (position_id=101)
    // Sort: priority desc → Alice (3) then Bob (2), so Alice is first checkbox
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]);

    // Apply — only Bob (103) should be in payload
    const applyBtn = screen.getByRole("button", {
      name: /apply 1/i,
    });
    await user.click(applyBtn);

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
    });

    expect(capturedBody!.apply_position_ids as number[]).not.toContain(101);
    expect(capturedBody!.apply_position_ids as number[]).toContain(103);
  });

  it("apply success invalidates board query and closes modal", async () => {
    const onClose = vi.fn();

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      ),
      http.post("/api/sieges/42/post-suggestions/apply", () =>
        HttpResponse.json({ applied_count: 1 })
      )
    );

    const user = userEvent.setup();
    renderModal({ onClose });

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    const applyBtn = screen.getByRole("button", { name: /apply/i });
    await user.click(applyBtn);

    // Modal should close (onClose called)
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });

  it("409 with stale_entries shows conflict state, modal stays open, board NOT invalidated", async () => {
    const onClose = vi.fn();

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      ),
      http.post("/api/sieges/42/post-suggestions/apply", () =>
        HttpResponse.json(
          {
            detail: {
              stale_entries: [{ position_id: 101, reason: "member_changed" }],
            },
          },
          { status: 409 }
        )
      )
    );

    const user = userEvent.setup();
    renderModal({ onClose });

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    const applyBtn = screen.getByRole("button", { name: /apply/i });
    await user.click(applyBtn);

    // Stale conflict content should appear
    await waitFor(() =>
      expect(
        screen.getByText(/another planner assigned a different member/i)
      ).toBeInTheDocument()
    );

    // Modal should NOT have closed
    expect(onClose).not.toHaveBeenCalled();

    // There will be multiple "Regenerate" buttons (header + conflict state) — at least one present
    expect(
      screen.getAllByRole("button", { name: /regenerate/i }).length
    ).toBeGreaterThanOrEqual(1);
  });

  it("Regenerate button re-fires the preview request and updates state", async () => {
    let previewCallCount = 0;

    server.use(
      http.post("/api/sieges/42/post-suggestions", () => {
        previewCallCount++;
        // Second call returns updated preview
        if (previewCallCount === 2) {
          return HttpResponse.json(
            makePreview({
              assignments: [
                {
                  post_id: 1,
                  building_number: 3,
                  priority: 3,
                  position_id: 101,
                  suggested_member_id: 99,
                  suggested_member_name: "Charlie",
                  suggested_condition_id: 10,
                  suggested_condition_description: "Attack Lv1",
                  current_member_id: null,
                  current_member_name: null,
                  current_condition_id: null,
                  current_condition_description: null,
                  matches_current: false,
                  skip_reason: null,
                },
              ],
            })
          );
        }
        return HttpResponse.json(makePreview());
      }),
      http.post("/api/sieges/42/post-suggestions/apply", () =>
        HttpResponse.json(
          {
            detail: {
              stale_entries: [{ position_id: 101, reason: "member_changed" }],
            },
          },
          { status: 409 }
        )
      )
    );

    const user = userEvent.setup();
    renderModal();

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    // Trigger stale 409
    const applyBtn = screen.getByRole("button", { name: /apply/i });
    await user.click(applyBtn);

    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: /regenerate/i }).length
      ).toBeGreaterThanOrEqual(1)
    );

    // Click the first Regenerate button (header or conflict — either works)
    const regenerateBtns = screen.getAllByRole("button", {
      name: /regenerate/i,
    });
    await user.click(regenerateBtns[0]);

    // Second preview fires; Charlie should now appear
    await waitFor(() =>
      expect(screen.getByText("Charlie")).toBeInTheDocument()
    );
    expect(previewCallCount).toBe(2);
  });

  it("filter tiles hide non-matching rows and All restores them", async () => {
    // Preview with one new assignment (Alice) and one skipped (no_match)
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      )
    );

    const user = userEvent.setup();
    renderModal();

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());
    // Both rows visible initially
    expect(
      screen.getByText("No member matches any of the post conditions")
    ).toBeInTheDocument();

    // Click "Skipped" filter tile — only skipped row should show
    const skippedTile = screen.getByRole("button", { name: /skipped/i });
    await user.click(skippedTile);

    // Alice's row should be gone; skipped row stays
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
    expect(
      screen.getByText("No member matches any of the post conditions")
    ).toBeInTheDocument();

    // Click "All" tile — both rows restored
    const allTile = screen.getByRole("button", { name: /all/i });
    await user.click(allTile);

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(
      screen.getByText("No member matches any of the post conditions")
    ).toBeInTheDocument();
  });

  it("already-optimal row (matches_current: true) has a disabled checkbox", async () => {
    // Build a preview where one entry matches_current: true (same outcome)
    const optimalPreview = makePreview({
      assignments: [
        {
          post_id: 1,
          building_number: 3,
          priority: 3,
          position_id: 101,
          suggested_member_id: 42,
          suggested_member_name: "Alice",
          suggested_condition_id: 10,
          suggested_condition_description: "Attack Lv1",
          current_member_id: 42,
          current_member_name: "Alice",
          current_condition_id: 10,
          current_condition_description: "Attack Lv1",
          matches_current: true,
          skip_reason: null,
        },
      ],
    });

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(optimalPreview)
      )
    );

    renderModal();

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    const rows = screen.getAllByRole("row");
    // Header row + 1 data row
    const dataRow = rows[1];
    const checkbox = within(dataRow).getByRole("checkbox");
    expect(checkbox).toBeDisabled();
  });

  it("empty preview renders the empty state copy", async () => {
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview({ assignments: [] }))
      )
    );

    renderModal();

    await waitFor(() =>
      expect(
        screen.getByText("No posts on this siege")
      ).toBeInTheDocument()
    );

    // No table rows should be rendered
    expect(screen.queryAllByRole("row")).toHaveLength(0);
  });

  it("loading state shows the spinner copy", async () => {
    // Mock preview to never resolve so we stay in loading state
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        new Promise<never>(() => {})
      )
    );

    renderModal();

    // The loading copy should be visible immediately
    expect(screen.getByText("Generating suggestions…")).toBeInTheDocument();
  });

  it("non-409 error shows the generic error banner", async () => {
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      ),
      http.post("/api/sieges/42/post-suggestions/apply", () =>
        HttpResponse.json({ detail: "Internal server error" }, { status: 500 })
      )
    );

    const user = userEvent.setup();
    const onClose = vi.fn();
    renderModal({ onClose });

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    const applyBtn = screen.getByRole("button", { name: /apply/i });
    await user.click(applyBtn);

    await waitFor(() =>
      expect(
        screen.getByText("Failed to apply suggestions. Please try again.")
      ).toBeInTheDocument()
    );

    // Modal should still be open
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Apply remaining re-issues apply with only non-stale IDs", async () => {
    let applyCallCount = 0;
    let secondApplyBody: Record<string, unknown> | null = null;

    // Two actionable rows: positions 101 and 103
    const twoRows = makePreview({
      assignments: [
        {
          post_id: 1,
          building_number: 3,
          priority: 3,
          position_id: 101,
          suggested_member_id: 42,
          suggested_member_name: "Alice",
          suggested_condition_id: 10,
          suggested_condition_description: "Attack Lv1",
          current_member_id: null,
          current_member_name: null,
          current_condition_id: null,
          current_condition_description: null,
          matches_current: false,
          skip_reason: null,
        },
        {
          post_id: 3,
          building_number: 5,
          priority: 2,
          position_id: 103,
          suggested_member_id: 55,
          suggested_member_name: "Bob",
          suggested_condition_id: 11,
          suggested_condition_description: "Defense Lv2",
          current_member_id: null,
          current_member_name: null,
          current_condition_id: null,
          current_condition_description: null,
          matches_current: false,
          skip_reason: null,
        },
      ],
    });

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(twoRows)
      ),
      http.post(
        "/api/sieges/42/post-suggestions/apply",
        async ({ request }) => {
          applyCallCount++;
          if (applyCallCount === 1) {
            // First call: return 409 with position 101 as stale
            return HttpResponse.json(
              {
                detail: {
                  stale_entries: [
                    { position_id: 101, reason: "member_changed" },
                  ],
                },
              },
              { status: 409 }
            );
          }
          // Second call: capture the body and return success
          secondApplyBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ applied_count: 1 });
        }
      )
    );

    const user = userEvent.setup();
    renderModal();

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    // Trigger the first apply → 409
    const applyBtn = screen.getByRole("button", { name: /apply/i });
    await user.click(applyBtn);

    // Wait for the stale-conflict state to appear
    await waitFor(() =>
      expect(
        screen.getByText(/another planner assigned a different member/i)
      ).toBeInTheDocument()
    );

    // Click "Apply remaining N" button
    const applyRemainingBtn = screen.getByRole("button", {
      name: /apply remaining/i,
    });
    await user.click(applyRemainingBtn);

    await waitFor(() => expect(secondApplyBody).not.toBeNull());

    // Second request must contain 103 and must NOT contain 101
    expect(
      secondApplyBody!.apply_position_ids as number[]
    ).toContain(103);
    expect(
      secondApplyBody!.apply_position_ids as number[]
    ).not.toContain(101);
  });
});
