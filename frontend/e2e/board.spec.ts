import { test, expect, type Page } from '@playwright/test';

/**
 * Board page: loading, tab switching, member bucket, validation dialog,
 * auto-fill preview, and position cell menu.
 *
 * Uses a helper that creates a siege if none exists.
 */

async function getOrCreateSiegeId(page: Page): Promise<string> {
  await page.goto('/sieges');

  const boardLink = page.getByRole('link', { name: 'Board' }).first();
  const exists = await boardLink.isVisible().catch(() => false);

  if (exists) {
    const href = await boardLink.getAttribute('href');
    const match = href?.match(/\/sieges\/(\d+)\/board/);
    if (match) return match[1];
  }

  // Create a new siege
  await page.goto('/sieges/new');
  await page.getByRole('button', { name: 'Create Siege' }).click();
  await page.waitForURL(/\/sieges\/\d+$/);
  const url = page.url();
  const match = url.match(/\/sieges\/(\d+)$/);
  return match ? match[1] : '1';
}

test.describe('Board page', () => {
  test('board page loads without error', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);
    await expect(page.getByRole('heading', { name: /board/i })).toBeVisible();
  });

  test('shows summary bar with slot counters', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);
    await expect(page.getByText(/total/i).first()).toBeVisible();
  });

  test('member bucket is visible', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);
    await expect(page.getByText('MEMBERS', { exact: true })).toBeVisible();
  });

  test('member bucket search input filters by name', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);

    const search = page.getByPlaceholder('Search...');
    await expect(search).toBeVisible();
    await search.fill('zzzzznosuchwmember');
    await expect(page.getByText('No members')).toBeVisible();
    await search.fill('');
  });

  test('Validate button opens validation dialog', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('button', { name: /validate/i }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: /validation results/i })).toBeVisible();

    await page.getByRole('button', { name: /close/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('Preview Auto-fill button opens preview dialog', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('button', { name: /preview auto-fill/i }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: /auto-fill preview/i })).toBeVisible();

    await page.getByRole('button', { name: /cancel/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('Back to Sieges link returns to list', async ({ page }) => {
    const siegeId = await getOrCreateSiegeId(page);
    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('link', { name: /back to sieges/i }).click();
    await expect(page).toHaveURL('/sieges');
    await expect(page.getByRole('heading', { name: 'Sieges' })).toBeVisible();
  });
});
