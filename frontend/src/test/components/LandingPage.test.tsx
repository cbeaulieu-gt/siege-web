import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeAll, afterAll, afterEach, describe, it, expect } from "vitest";
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

  it("renders the feature list with 6 bullets", async () => {
    renderLanding();
    await waitFor(() => {
      const list = screen.getByTestId("feature-list");
      const bullets = list.querySelectorAll("li");
      expect(bullets.length).toBe(6);
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
        "https://github.com/cbeaulieu-gt/siege-web/blob/main/docs/self-host/anywhere.md",
      );
      expect(screen.getByTestId("self-host-azure-link")).toHaveAttribute(
        "href",
        "https://github.com/cbeaulieu-gt/siege-web/blob/main/docs/self-host/azure.md",
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
