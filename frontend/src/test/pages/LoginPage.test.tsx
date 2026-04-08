import { screen, waitFor } from "@testing-library/react";
import { beforeAll, afterAll, afterEach, describe, it, expect } from "vitest";
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

  it("shows unauthorized error message", async () => {
    renderWithProviders(<LoginPage />, {
      initialEntries: ["/login?error=unauthorized"],
    });
    await waitFor(() => {
      expect(
        screen.getByText(/not authorized to access this app/i)
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
