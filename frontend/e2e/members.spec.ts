import { test, expect, request as playwrightRequest } from '@playwright/test';

/**
 * Members tests — list, filter, create, and navigate to detail.
 *
 * Each test that creates data uses a timestamp-suffixed name so it is unique
 * even when the DB is not reset between runs.
 *
 * If the 30-active-member limit is reached in the DB, a beforeAll hook
 * deactivates the active member with the highest id to free a slot. The freed
 * member stays deactivated after the suite (test-DB concern).
 */

const ACTIVE_MEMBER_LIMIT = 30;

/**
 * Ensure there are at least `needed` free active-member slots.
 * Deactivates the active members with the highest ids to free slots.
 */
async function ensureMemberSlotsAvailable(needed = 5): Promise<void> {
  const ctx = await playwrightRequest.newContext({ baseURL: 'http://localhost:8000' });
  try {
    const listRes = await ctx.get('/api/members?is_active=true');
    if (listRes.status() !== 200) return;
    const active: Array<{ id: number; name: string }> = await listRes.json();
    const available = ACTIVE_MEMBER_LIMIT - active.length;
    if (available >= needed) return;
    // Deactivate the `(needed - available)` members with the highest ids.
    const toFree = [...active]
      .sort((a, b) => b.id - a.id)
      .slice(0, needed - available);
    for (const m of toFree) {
      await ctx.delete(`/api/members/${m.id}`);
    }
  } finally {
    await ctx.dispose();
  }
}

test.beforeAll(async () => {
  // Free 5 slots for the member-creation tests in this suite.
  await ensureMemberSlotsAvailable(5);
});

// ── Page structure ──────────────────────────────────────────────────────────────

test.describe('Members', () => {
  // ── Page structure ──────────────────────────────────────────────────────────

  test('members page loads with heading', async ({ page }) => {
    await page.goto('/members');
    await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  });

  test('shows Add Member button', async ({ page }) => {
    await page.goto('/members');
    await expect(page.getByRole('button', { name: 'Add Member' })).toBeVisible();
  });

  test('role filter dropdown is present', async ({ page }) => {
    await page.goto('/members');
    // The Select trigger shows "All Roles" by default
    await expect(page.getByText('All Roles')).toBeVisible();
  });

  test('active-only checkbox is checked by default', async ({ page }) => {
    await page.goto('/members');
    const checkbox = page.getByRole('checkbox', { name: /active only/i });
    await expect(checkbox).toBeChecked();
  });

  // ── Navigation ──────────────────────────────────────────────────────────────

  test('Add Member button navigates to new member form', async ({ page }) => {
    await page.goto('/members');
    await page.getByRole('button', { name: 'Add Member' }).click();
    await expect(page).toHaveURL('/members/new');
    await expect(page.getByRole('heading', { name: /add member/i })).toBeVisible();
  });

  // ── Create member ───────────────────────────────────────────────────────────

  test('creates a new member and they appear in the list', async ({ page }) => {
    const name = `E2E-Member-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    await page.goto('/members/new');

    // Fill the name field (label is "Name")
    await page.getByLabel('Name', { exact: true }).fill(name);

    // Role defaults to Novice — keep it; just save
    await page.getByRole('button', { name: /^save$/i }).click();

    // After creation the app redirects to the member detail page
    await expect(page).toHaveURL(/\/members\/\d+$/);

    // Navigate back to the list and confirm the name is visible
    await page.goto('/members');
    // New members are active, so they show with the active-only filter on
    await expect(page.getByText(name)).toBeVisible();
  });

  test('creates a member with Heavy Hitter role', async ({ page }) => {
    const name = `E2E-HH-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    await page.goto('/members/new');
    await page.getByLabel('Name', { exact: true }).fill(name);

    // Open the Role select and pick Heavy Hitter
    await page.getByRole('combobox', { name: /role/i }).click();
    await page.getByRole('option', { name: 'Heavy Hitter' }).click();

    await page.getByRole('button', { name: /^save$/i }).click();
    await expect(page).toHaveURL(/\/members\/\d+$/);

    // Badge should reflect the role on the detail page
    await expect(page.getByText('Heavy Hitter')).toBeVisible();
  });

  // ── Detail page ─────────────────────────────────────────────────────────────

  test('clicking Edit / Preferences link opens member detail', async ({ page }) => {
    // Ensure at least one member exists (uncheck active-only to widen the net)
    await page.goto('/members');
    const activeCheckbox = page.getByRole('checkbox', { name: /active only/i });
    if (await activeCheckbox.isChecked()) {
      await activeCheckbox.uncheck();
    }

    // Wait for rows to load — skip the header row
    const editLinks = page.getByRole('link', { name: /edit \/ preferences/i });
    const linkCount = await editLinks.count();
    if (linkCount === 0) {
      // No members at all yet — create one first and then proceed
      await page.goto('/members/new');
      await page.getByLabel('Name', { exact: true }).fill(`E2E-Nav-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`);
      await page.getByRole('button', { name: /^save$/i }).click();
      await expect(page).toHaveURL(/\/members\/\d+$/);
      return; // landing on detail page is sufficient
    }

    await editLinks.first().click();
    await expect(page).toHaveURL(/\/members\/\d+$/);
    await expect(page.getByLabel('Name', { exact: true })).toBeVisible();
  });

  test('member detail page shows Back to Members link', async ({ page }) => {
    // Create a member so we have a detail URL to visit
    const name = `E2E-Back-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    await page.goto('/members/new');
    await page.getByLabel('Name', { exact: true }).fill(name);
    await page.getByRole('button', { name: /^save$/i }).click();
    await expect(page).toHaveURL(/\/members\/\d+$/);

    await page.getByRole('link', { name: /back to members/i }).click();
    await expect(page).toHaveURL('/members');
    await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  });

  // ── Deactivate ──────────────────────────────────────────────────────────────

  test('deactivate button appears on existing active member detail page', async ({ page }) => {
    const name = `E2E-Deact-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    await page.goto('/members/new');
    await page.getByLabel('Name', { exact: true }).fill(name);
    await page.getByRole('button', { name: /^save$/i }).click();
    await expect(page).toHaveURL(/\/members\/\d+$/);

    // After create we're on the detail page already
    await expect(page.getByRole('button', { name: /deactivate/i })).toBeVisible();
  });
});
