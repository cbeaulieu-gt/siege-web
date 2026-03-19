import { test, expect } from '@playwright/test';

/**
 * Siege lifecycle: create → settings → navigate to board/members/posts.
 *
 * Assumptions:
 *   - The app is running at baseURL with a seeded or empty database.
 *   - Creating a siege lands on the settings page (/sieges/:id).
 */
test.describe('Siege lifecycle', () => {
  test('creates a new siege and navigates to settings', async ({ page }) => {
    await page.goto('/sieges');
    await expect(page.getByRole('heading', { name: 'Sieges' })).toBeVisible();

    await page.getByRole('button', { name: 'New Siege' }).click();
    await expect(page.getByRole('heading', { name: 'New Siege' })).toBeVisible();

    // Submit with the auto-suggested date
    await page.getByRole('button', { name: 'Create Siege' }).click();

    // Should land on siege settings page (SiegeLayout renders the settings index)
    await expect(page).toHaveURL(/\/sieges\/\d+$/);
  });

  test('siege row appears in the list after creation', async ({ page }) => {
    await page.goto('/sieges');

    const beforeCount = await page.getByRole('row').count();

    await page.getByRole('button', { name: 'New Siege' }).click();
    await page.getByRole('button', { name: 'Create Siege' }).click();
    await expect(page).toHaveURL(/\/sieges\/\d+$/);

    await page.goto('/sieges');
    const afterCount = await page.getByRole('row').count();
    expect(afterCount).toBeGreaterThan(beforeCount);
  });

  test('siege settings page shows Board / Posts / Members links', async ({ page }) => {
    await page.goto('/sieges/new');
    await page.getByRole('button', { name: 'Create Siege' }).click();
    await expect(page).toHaveURL(/\/sieges\/\d+$/);

    // The SiegeLayout navigation tabs
    await expect(page.getByRole('link', { name: /board/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /posts/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /members/i })).toBeVisible();
  });

  test('navigates from sieges list to board via link', async ({ page }) => {
    await page.goto('/sieges');

    const boardLink = page.getByRole('link', { name: 'Board' }).first();
    await expect(boardLink).toBeVisible();
    await boardLink.click();
    await expect(page).toHaveURL(/\/sieges\/\d+\/board$/);
  });

  test('siege list shows Planning status badge', async ({ page }) => {
    await page.goto('/sieges');
    await expect(page.getByText('Planning').first()).toBeVisible();
  });
});
