import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeAll, afterAll, afterEach, describe, it, expect } from "vitest";
import { server } from "../server";
import { renderWithProviders } from "../utils";
import { useAuth } from "../../context/AuthContext";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function TestConsumer() {
  const { user, isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div>Loading...</div>;
  if (!isAuthenticated) return <div>Not authenticated</div>;
  return <div>Hello {user?.name}</div>;
}

describe("AuthContext", () => {
  it("shows loading state initially then resolves to authenticated", async () => {
    // Default handler returns authenticated user
    renderWithProviders(<TestConsumer />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Hello TestUser")).toBeInTheDocument();
    });
  });

  it("resolves to not authenticated on 401", async () => {
    server.use(
      http.get("/api/auth/me", () => new HttpResponse(null, { status: 401 }))
    );
    renderWithProviders(<TestConsumer />);
    await waitFor(() => {
      expect(screen.getByText("Not authenticated")).toBeInTheDocument();
    });
  });
});
