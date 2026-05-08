import { screen, waitFor } from "@testing-library/react";
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
import { renderWithProviders } from "../utils";
import { server } from "../server";
import ChangelogDropdown from "../../components/ChangelogDropdown";

// ---------------------------------------------------------------------------
// virtual:changelog mock
// ---------------------------------------------------------------------------
// Vitest's module mock supports virtual modules — the second argument to
// vi.mock() receives a factory so we don't need the module to exist on disk.
vi.mock("virtual:changelog", () => ({
  changelog: [
    {
      version: "1.2.0",
      releaseDate: "2026-05-01",
      sections: {
        Added: ["New siege board drag-and-drop", "Member import from Excel"],
        Fixed: ["Post sorting was reversed"],
      },
    },
    {
      version: "1.1.0",
      releaseDate: "2026-04-15",
      sections: {
        Added: ["Post conditions filter"],
        Fixed: ["Auth redirect loop on logout"],
      },
    },
    {
      version: "0.9.0",
      releaseDate: "2026-03-01",
      sections: {
        Added: ["Initial release"],
      },
    },
  ],
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Render just the ChangelogDropdown in isolation (no Layout wrapper needed).
 * The renderWithProviders helper supplies QueryClient + MemoryRouter + AuthProvider.
 */
function renderDropdown() {
  return renderWithProviders(<ChangelogDropdown />);
}

// Latest fixture entry releaseDate — used in date-comparison assertions.
const LATEST_RELEASE = "2026-05-01";

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ---------------------------------------------------------------------------
// AC #1 & #2 — indicator shown
// ---------------------------------------------------------------------------

describe("ChangelogDropdown — unread indicator", () => {
  it("shows the red dot when last_seen_changelog_at is null (never seen)", async () => {
    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: null })
      )
    );

    renderDropdown();

    await waitFor(() => {
      expect(screen.getByTestId("changelog-unread-dot")).toBeInTheDocument();
    });
  });

  it("shows the red dot when last_seen_changelog_at is older than latest release", async () => {
    // Older than LATEST_RELEASE (2026-05-01)
    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: "2026-04-30T12:00:00" })
      )
    );

    renderDropdown();

    await waitFor(() => {
      expect(screen.getByTestId("changelog-unread-dot")).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // AC #3 — indicator hidden
  // ---------------------------------------------------------------------------

  it("hides the red dot when last_seen_changelog_at is newer than the latest release", async () => {
    // Newer than LATEST_RELEASE (2026-05-01) — already seen
    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: "2026-05-02T00:00:00" })
      )
    );

    renderDropdown();

    // Wait for the query to resolve — once the query returns a "seen" value
    // the dot must disappear. We allow time for the status fetch to complete.
    await waitFor(() => {
      expect(
        screen.queryByTestId("changelog-unread-dot")
      ).not.toBeInTheDocument();
    });
  });

  it("hides the red dot when last_seen_changelog_at equals the latest release date", async () => {
    // Exactly matching — count as seen.
    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({
          last_seen_changelog_at: `${LATEST_RELEASE}T00:00:00`,
        })
      )
    );

    renderDropdown();

    await waitFor(() => {
      expect(
        screen.queryByTestId("changelog-unread-dot")
      ).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// AC #4 — dropdown renders multiple entries
// ---------------------------------------------------------------------------

describe("ChangelogDropdown — dropdown content", () => {
  beforeAll(() => {
    // Use null so the indicator is visible, making it easy to confirm open state.
    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: null })
      ),
      http.post("/api/changelog/mark-seen", () =>
        HttpResponse.json({ last_seen_changelog_at: new Date().toISOString() })
      )
    );
  });

  it("renders all three fixture entries with version, releaseDate, and section bullets", async () => {
    const user = userEvent.setup();
    renderDropdown();

    // Wait for status query to resolve before clicking.
    await waitFor(() =>
      expect(screen.getByTestId("changelog-button")).toBeInTheDocument()
    );

    await user.click(screen.getByTestId("changelog-button"));

    // Version headings
    expect(await screen.findByText(/1\.2\.0/)).toBeInTheDocument();
    expect(screen.getByText(/1\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/0\.9\.0/)).toBeInTheDocument();

    // Release date headings
    expect(screen.getByText(/2026-05-01/)).toBeInTheDocument();
    expect(screen.getByText(/2026-04-15/)).toBeInTheDocument();
    expect(screen.getByText(/2026-03-01/)).toBeInTheDocument();

    // Section bullets from the first two entries
    expect(
      screen.getByText(/New siege board drag-and-drop/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Post conditions filter/)).toBeInTheDocument();
    expect(screen.getByText(/Initial release/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AC #5 — mark-seen called once on first open
// ---------------------------------------------------------------------------

describe("ChangelogDropdown — mark-seen behaviour", () => {
  it("fires POST /api/changelog/mark-seen exactly once when the dropdown is opened", async () => {
    const user = userEvent.setup();
    let markSeenCallCount = 0;

    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: null })
      ),
      http.post("/api/changelog/mark-seen", () => {
        markSeenCallCount += 1;
        return HttpResponse.json({
          last_seen_changelog_at: new Date().toISOString(),
        });
      })
    );

    renderDropdown();

    await waitFor(() =>
      expect(screen.getByTestId("changelog-button")).toBeInTheDocument()
    );

    await user.click(screen.getByTestId("changelog-button"));

    await waitFor(() => {
      expect(markSeenCallCount).toBe(1);
    });
  });

  // ---------------------------------------------------------------------------
  // AC #6 — no double-call within a session
  // ---------------------------------------------------------------------------

  it("does NOT fire mark-seen a second time when the dropdown is closed and reopened", async () => {
    const user = userEvent.setup();
    let markSeenCallCount = 0;

    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: null })
      ),
      http.post("/api/changelog/mark-seen", () => {
        markSeenCallCount += 1;
        return HttpResponse.json({
          last_seen_changelog_at: new Date().toISOString(),
        });
      })
    );

    renderDropdown();

    await waitFor(() =>
      expect(screen.getByTestId("changelog-button")).toBeInTheDocument()
    );

    // First open — should fire once.
    await user.click(screen.getByTestId("changelog-button"));
    await waitFor(() => expect(markSeenCallCount).toBe(1));

    // Close via Escape key (Radix sets pointer-events:none on the trigger
    // while the menu is open, so clicking the trigger again won't work in
    // jsdom — keyboard close is the correct approach).
    await user.keyboard("{Escape}");

    // Wait for the dropdown to close (the content should unmount).
    await waitFor(() => {
      expect(screen.queryByText(/1\.2\.0/)).not.toBeInTheDocument();
    });

    // Reopen — should NOT fire again.
    await user.click(screen.getByTestId("changelog-button"));

    // Give any pending async work time to settle.
    await waitFor(() => {
      expect(markSeenCallCount).toBe(1);
    });
  });

  // ---------------------------------------------------------------------------
  // AC #7 — optimistic clear on open
  // ---------------------------------------------------------------------------

  it("clears the unread indicator immediately when the button is clicked (optimistic)", async () => {
    const user = userEvent.setup();

    // Hang the mark-seen POST indefinitely so we can assert the optimistic
    // state before the network resolves.
    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: null })
      ),
      http.post("/api/changelog/mark-seen", () => new Promise(() => {}))
    );

    renderDropdown();

    // Confirm indicator is visible before click.
    await waitFor(() =>
      expect(screen.getByTestId("changelog-unread-dot")).toBeInTheDocument()
    );

    // Click — optimistic update should hide the dot before network resolves.
    await user.click(screen.getByTestId("changelog-button"));

    // The dot must be gone synchronously (no waitFor needed, but we use it
    // to allow one React render cycle).
    await waitFor(() => {
      expect(
        screen.queryByTestId("changelog-unread-dot")
      ).not.toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // AC #8 — rollback on POST failure
  // ---------------------------------------------------------------------------

  it("restores the unread indicator when mark-seen POST fails", async () => {
    const user = userEvent.setup();

    server.use(
      http.get("/api/changelog/status", () =>
        HttpResponse.json({ last_seen_changelog_at: null })
      ),
      http.post("/api/changelog/mark-seen", () => HttpResponse.error())
    );

    renderDropdown();

    // Wait for indicator to appear.
    await waitFor(() =>
      expect(screen.getByTestId("changelog-unread-dot")).toBeInTheDocument()
    );

    // Click — optimistic clear happens first.
    await user.click(screen.getByTestId("changelog-button"));

    // After the POST fails, indicator should reappear.
    await waitFor(() => {
      expect(screen.getByTestId("changelog-unread-dot")).toBeInTheDocument();
    });
  });
});
