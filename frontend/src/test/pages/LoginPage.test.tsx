import { screen, waitFor } from "@testing-library/react";
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
import LoginPage from "../../pages/LoginPage";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("LoginPage", () => {
  it("renders the sign-in button and privacy disclosure", async () => {
    renderWithProviders(<LoginPage />, { initialEntries: ["/login"] });
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /sign in with discord/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/username and avatar/i)).toBeInTheDocument();
  });

  it("shows membership-denial reframe for ?error=unauthorized", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=unauthorized"],
    });
    await waitFor(() => {
      // unauthorized is now routed to the soft-handoff banner, not the generic error
      expect(
        screen.getByText(/private to Master/i)
      ).toBeInTheDocument();
    });
  });

  it("shows service unavailable error message", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=service_unavailable"],
    });
    await waitFor(() => {
      expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
    });
  });

  it("shows generic error for unknown error codes", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=invalid_state"],
    });
    await waitFor(() => {
      expect(
        screen.getByText(/not authorized to access this app/i)
      ).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Mobile banner
// ---------------------------------------------------------------------------

describe("LoginPage — mobile banner", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the mobile warning banner when innerWidth < 768", async () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(375);
    renderWithProviders(<LoginPage />, { initialEntries: ["/login"] });
    await waitFor(() => {
      expect(
        screen.getByText(/Desktop recommended/i)
      ).toBeInTheDocument();
    });
  });

  it("does not render the mobile warning banner when innerWidth >= 768", async () => {
    vi.spyOn(window, "innerWidth", "get").mockReturnValue(1280);
    renderWithProviders(<LoginPage />, { initialEntries: ["/login"] });
    // Give the component a chance to render; the banner must be absent.
    await waitFor(() => {
      expect(
        screen.queryByText(/Desktop recommended/i)
      ).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Rejection reframe
// ---------------------------------------------------------------------------

describe("LoginPage — rejection reframe", () => {
  it("shows the private-instance message and self-host link on ?error=unauthorized", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=unauthorized"],
    });
    await waitFor(() => {
      // Match on unambiguous fragment to avoid apostrophe/rsquo encoding differences
      expect(
        screen.getByText(/private to Master/i)
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("link", {
        name: /Run Siege Assignments for your own clan/i,
      })
    ).toBeInTheDocument();
  });

  it("renders the always-visible self-host link on the happy path too", async () => {
    renderWithProviders(<LoginPage />, { initialEntries: ["/login"] });
    await waitFor(() => {
      expect(
        screen.getByRole("link", {
          name: /Run Siege Assignments for your own clan/i,
        })
      ).toBeInTheDocument();
    });
  });
});
