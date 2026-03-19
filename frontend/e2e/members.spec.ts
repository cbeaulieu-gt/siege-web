import { test, expect } from '@playwright/test';

/**
 * Members page: list, filter, create, and view a member.
 */
test.describe('Members', () => {
  test('members page loads and shows heading', async ({ page }) => {
    await page.goto('/members');
    await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  });

  test('shows Add Member button', async ({ page }) => {
    await page.goto('/members');
    await expect(page.getByRole('button', { name: 'Add Member' })).toBeVisible();
  });

  test('role filter dropdown is present', async ({ page }) => {
    await page.goto('/members');
    await expect(page.getByText('All Roles')).toBeVisible();
  });

  test('active-only checkbox is checked by default', async ({ page }) => {
    await page.goto('/members');
    const checkbox = page.getByRole('checkbox', { name: /active only/i });
    await expect(checkbox).toBeChecked();
  });

  test('navigates to new member form', async ({ page }) => {
    await page.goto('/members');
    await page.getByRole('button', { name: 'Add Member' }).click();
    await expect(page).toHaveURL('/members/new');
    await expect(page.getByRole('heading', { name: /add member|new member/i })).toBeVisible();
  });

  test('creates a new member and shows them in the list', async ({ page }) => {
    const uniqueName = `TestMember-${Date.now()}`;

    await page.goto('/members/new');
    await page.getByLabel(/name/i).fill(uniqueName);

    // Role is required — select Heavy Hitter
    await page.getByRole('combobox', { name: /role/i }).click();
    await page.getByRole('option', { name: 'Heavy Hitter' }).click();

    await page.getByRole('button', { name: /save|create|add/i }).click();

    // Should redirect to members list or member detail
    await expect(page).toHaveURL(/\/members(\/\d+)?$/);

    await page.goto('/members');
    await page.getByLabel(/active only/i).uncheck();
    await expect(page.getByText(uniqueName)).toBeVisible();
  });

  test('clicking a member row opens detail page', async ({ page }) => {
    await page.goto('/members');
    await page.getByLabel(/active only/i).uncheck();

    const firstRow = page.getByRole('row').nth(1); // skip header
    const nameCell = firstRow.getByRole('cell').first();
    const name = await nameCell.textContent();

    await firstRow.click();
    await expect(page).toHaveURL(/\/members\/\d+$/);
    if (name) {
      await expect(page.getByText(name.trim())).toBeVisible();
    }
  });
});
