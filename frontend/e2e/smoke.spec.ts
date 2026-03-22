import { test, expect } from '@playwright/test';

/**
 * Smoke tests — verify the app is reachable and the backend is healthy.
 * These intentionally make no assumptions about DB state.
 */
test.describe('Smoke', () => {
  test('app loads and redirects / to /sieges', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL('/sieges');
    // The main nav brand is always present
    await expect(page.getByText('Siege Assignments')).toBeVisible();
  });

  test('backend health endpoint returns healthy', async ({ request }) => {
    const res = await request.get('/api/health');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toMatchObject({ status: 'healthy' });
  });

  test('sieges page renders heading and New Siege button', async ({ page }) => {
    await page.goto('/sieges');
    await expect(page.getByRole('heading', { name: 'Sieges' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'New Siege' })).toBeVisible();
  });

  test('members page renders heading and Add Member button', async ({ page }) => {
    await page.goto('/members');
    await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add Member' })).toBeVisible();
  });

  test('top navigation links are all present', async ({ page }) => {
    await page.goto('/sieges');
    await expect(page.getByRole('link', { name: 'Sieges' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Members' })).toBeVisible();
  });
});
