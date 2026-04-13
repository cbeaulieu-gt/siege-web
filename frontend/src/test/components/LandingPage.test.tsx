import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeAll, afterAll, afterEach, describe, it, expect, vi, beforeEach } from "vitest";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../utils";
import { server } from "../server";
import { LandingOrSieges } from "../../pages/LandingPage";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderLanding(initialPath = "/") {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<LandingOrSieges />} />
      {/* stub /sieges so Navigate target exists */}
      <Route path="/sieges" element={<div>Sieges page</div>} />
    </Routes>,
    { initialEntries: [initialPath] },
  );
}

// ---------------------------------------------------------------------------
// Anonymous user — landing page content
// ---------------------------------------------------------------------------

describe("LandingPage (anonymous user)", () => {
  // Override before each test because afterEach (outer) resets handlers.
  beforeEach(() => {
    server.use(
      http.get("/api/auth/me", () =>
        HttpResponse.json({ detail: "Not authenticated" }, { status: 401 }),
      ),
    );
  });

  it("renders the hero headline", async () => {
    renderLanding();
    await waitFor(() => {
      expect(
        screen.getByText(/A siege assignment tool I built/i),
      ).toBeInTheDocument();
    });
  });

  it("renders the Sign in CTA linking to /login", async () => {
    renderLanding();
    await waitFor(() => {
      const signIn = screen.getByRole("link", { name: /sign in/i });
      expect(signIn).toBeInTheDocument();
      expect(signIn).toHaveAttribute("href", "/login");
    });
  });

  it("renders the hero CTA that targets #self-host", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByTestId("hero-cta")).toBeInTheDocument();
    });
  });

  it("renders the feature list with 9 bullets", async () => {
    renderLanding();
    await waitFor(() => {
      const list = screen.getByTestId("feature-list");
      const bullets = list.querySelectorAll("li");
      expect(bullets.length).toBe(9);
    });
  });

  it("renders the board screenshot placeholder", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByTestId("board-screenshot")).toBeInTheDocument();
    });
  });

  it("renders the Under the hood section with three service cards", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByText("siege-api")).toBeInTheDocument();
      expect(screen.getByText("siege-frontend")).toBeInTheDocument();
      expect(screen.getByText("siege-bot")).toBeInTheDocument();
    });
  });

  it("renders the self-host section with all three cards", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByTestId("self-host-local-link")).toBeInTheDocument();
      expect(screen.getByTestId("self-host-anywhere-link")).toBeInTheDocument();
      expect(screen.getByTestId("self-host-azure-link")).toBeInTheDocument();
    });
  });

  it("self-host anywhere card has Recommended badge", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByText("Recommended")).toBeInTheDocument();
    });
  });

  it("self-host links point to the correct GitHub doc URLs", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByTestId("self-host-anywhere-link")).toHaveAttribute(
        "href",
        "https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Any-VPS",
      );
      expect(screen.getByTestId("self-host-azure-link")).toHaveAttribute(
        "href",
        "https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure",
      );
    });
  });

  it("renders contact section with Discord handle and GitHub link", async () => {
    renderLanding();
    await waitFor(() => {
      expect(screen.getByText("higgsbp")).toBeInTheDocument();
      const ghLink = screen.getByRole("link", {
        name: /github.com\/cbeaulieu-gt\/siege-web/i,
      });
      expect(ghLink).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Authenticated user — redirect to /sieges
// ---------------------------------------------------------------------------

describe("LandingOrSieges (authenticated user)", () => {
  it("redirects to /sieges when user is authenticated", async () => {
    // Default handler already returns a logged-in user
    renderLanding();
    await waitFor(() => {
      expect(screen.getByText("Sieges page")).toBeInTheDocument();
    });
  });

  it("does not render landing page content when authenticated", async () => {
    renderLanding();
    await waitFor(() => {
      expect(
        screen.queryByText(/A siege assignment tool I built/i),
      ).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Loading state — LandingOrSieges returns null while auth check is in flight
// ---------------------------------------------------------------------------

describe("LandingOrSieges (loading state)", () => {
  it("renders nothing while the auth check is pending", () => {
    // Hang the /api/auth/me request indefinitely so isLoading stays true.
    server.use(
      http.get("/api/auth/me", () => new Promise(() => {})),
    );
    renderLanding();
    // Neither landing content nor the redirect target should appear.
    expect(
      screen.queryByText(/A siege assignment tool I built/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Sieges page")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Hero CTA — smooth-scrolls to the self-host section
// ---------------------------------------------------------------------------

describe("LandingPage hero CTA", () => {
  beforeEach(() => {
    server.use(
      http.get("/api/auth/me", () =>
        HttpResponse.json({ detail: "Not authenticated" }, { status: 401 }),
      ),
    );
  });

  it("calls scrollIntoView with smooth behavior when CTA is clicked", async () => {
    const user = userEvent.setup();
    const scrollIntoViewMock = vi.fn();
    // jsdom does not implement scrollIntoView; install a mock before render.
    Element.prototype.scrollIntoView = scrollIntoViewMock;

    renderLanding();

    const cta = await screen.findByTestId("hero-cta");
    await user.click(cta);

    expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth" });
  });
});
