import { type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import { AuthProvider } from "../context/AuthContext";

interface TestRenderOptions extends Omit<RenderOptions, "wrapper"> {
  initialEntries?: MemoryRouterProps["initialEntries"];
}

export function renderWithProviders(
  ui: ReactNode,
  { initialEntries = ["/"], ...renderOptions }: TestRenderOptions = {}
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>{children}</AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

export * from "@testing-library/react";
