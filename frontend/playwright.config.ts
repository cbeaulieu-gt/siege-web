import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for siege-web e2e tests.
 *
 * Tests run against a locally running full stack (frontend on :5173, backend on
 * :8000).  Start the stack with `docker-compose up` before running.
 *
 * Environment variables:
 *   PLAYWRIGHT_BASE_URL  – override the default base URL (default: http://localhost:5173)
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // sequential — tests share a real DB
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
