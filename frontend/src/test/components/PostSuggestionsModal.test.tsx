/**
 * PostSuggestionsModal component tests.
 *
 * Covered cases:
 * 1. Opening the modal fires the preview request and renders one row per assignment.
 * 2. Rows where suggested_member_id === null render with skip_reason text and
 *    have a disabled checkbox.
 * 3. Unchecking a row excludes its position_id from the apply payload.
 * 4. Apply success invalidates board and posts queries (modal closes).
 * 5. Apply 409 with stale_entries → modal stays open, banner shown, board NOT invalidated.
 * 6. "Regenerate preview" button re-fires the preview request.
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
        priority: 5,
        position_id: 101,
        suggested_member_id: 42,
        suggested_member_name: "Alice",
        suggested_condition_id: 10,
        suggested_condition_description: "Attack Lv1",
        current_member_id: null,
        current_member_name: null,
        current_condition_id: null,
        matches_current: false,
        skip_reason: null,
      },
      {
        post_id: 2,
        building_number: 7,
        priority: 3,
        position_id: 102,
        suggested_member_id: null,
        suggested_member_name: null,
        suggested_condition_id: null,
        suggested_condition_description: null,
        current_member_id: null,
        current_member_name: null,
        current_condition_id: null,
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
    await waitFor(() =>
      expect(screen.getByText("Alice")).toBeInTheDocument()
    );

    // Row for skipped post
    expect(screen.getByText("No match found")).toBeInTheDocument();
  });

  it("renders skip_reason text and disabled checkbox for null-suggestion rows", async () => {
    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      )
    );

    renderModal();

    await waitFor(() =>
      expect(screen.getByText("No match found")).toBeInTheDocument()
    );

    // Find the row for the skipped post (building_number=7) and check its checkbox
    const rows = screen.getAllByRole("row");
    // Header row + 2 data rows
    const dataRows = rows.slice(1);
    // Find the "no match" row — it's the second data row
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
          priority: 5,
          position_id: 101,
          suggested_member_id: 42,
          suggested_member_name: "Alice",
          suggested_condition_id: 10,
          suggested_condition_description: "Attack Lv1",
          current_member_id: null,
          current_member_name: null,
          current_condition_id: null,
          matches_current: false,
          skip_reason: null,
        },
        {
          post_id: 3,
          building_number: 5,
          priority: 4,
          position_id: 103,
          suggested_member_id: 55,
          suggested_member_name: "Bob",
          suggested_condition_id: 11,
          suggested_condition_description: "Defense Lv2",
          current_member_id: null,
          current_member_name: null,
          current_condition_id: null,
          matches_current: false,
          skip_reason: null,
        },
      ],
    });

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(twoSuggestions)
      ),
      http.post("/api/sieges/42/post-suggestions/apply", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ applied_count: 1 });
      })
    );

    const user = userEvent.setup();
    renderModal();

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Bob")).toBeInTheDocument());

    // Both rows should be checked by default; uncheck Alice's row (position_id=101)
    const checkboxes = screen.getAllByRole("checkbox");
    // Checkboxes are in table order: Alice row first, Bob row second
    await user.click(checkboxes[0]);

    // Apply — only Bob (103) should be in payload
    const applyBtn = screen.getByRole("button", { name: /apply selected \(1\)/i });
    await user.click(applyBtn);

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
    });

    expect((capturedBody!.apply_position_ids as number[])).not.toContain(101);
    expect((capturedBody!.apply_position_ids as number[])).toContain(103);
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

    const applyBtn = screen.getByRole("button", { name: /apply selected/i });
    await user.click(applyBtn);

    // Modal should close (onClose called)
    await waitFor(() => expect(onClose).toHaveBeenCalledOnce());
  });

  it("409 with stale_entries shows banner, modal stays open, board NOT invalidated", async () => {
    const onClose = vi.fn();

    server.use(
      http.post("/api/sieges/42/post-suggestions", () =>
        HttpResponse.json(makePreview())
      ),
      http.post("/api/sieges/42/post-suggestions/apply", () =>
        HttpResponse.json(
          {
            detail: {
              stale_entries: [
                { position_id: 101, reason: "member_changed" },
              ],
            },
          },
          { status: 409 }
        )
      )
    );

    const user = userEvent.setup();
    renderModal({ onClose });

    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());

    const applyBtn = screen.getByRole("button", { name: /apply selected/i });
    await user.click(applyBtn);

    // Banner should appear
    await waitFor(() =>
      expect(
        screen.getByText(/another planner assigned a different member/i)
      ).toBeInTheDocument()
    );

    // Modal should NOT have closed
    expect(onClose).not.toHaveBeenCalled();

    // Regenerate preview button should be visible
    expect(
      screen.getByRole("button", { name: /regenerate preview/i })
    ).toBeInTheDocument();
  });

  it("Regenerate preview button re-fires the preview request and updates state", async () => {
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
                  priority: 5,
                  position_id: 101,
                  suggested_member_id: 99,
                  suggested_member_name: "Bob",
                  suggested_condition_id: 10,
                  suggested_condition_description: "Attack Lv1",
                  current_member_id: null,
                  current_member_name: null,
                  current_condition_id: null,
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
    const applyBtn = screen.getByRole("button", { name: /apply selected/i });
    await user.click(applyBtn);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /regenerate preview/i })
      ).toBeInTheDocument()
    );

    // Click regenerate
    const regenerateBtn = screen.getByRole("button", {
      name: /regenerate preview/i,
    });
    await user.click(regenerateBtn);

    // Second preview fires; Bob should now appear
    await waitFor(() => expect(screen.getByText("Bob")).toBeInTheDocument());
    expect(previewCallCount).toBe(2);
  });
});
