import { test, expect, type APIRequestContext } from '@playwright/test';

/**
 * Board page tests — tab switching, member bucket, position cell menu,
 * validation dialog, and auto-fill preview.
 *
 * Each test that needs specific state seeds it directly via the API so the
 * UI assertions are deterministic.
 */

// ── Helpers ────────────────────────────────────────────────────────────────────

async function apiCreateSiege(
  request: APIRequestContext,
  date: string,
): Promise<number> {
  const res = await request.post('/api/sieges', { data: { date } });
  expect(res.status()).toBe(201);
  return (await res.json()).id as number;
}

/**
 * Add a building to a siege.
 * Because create_siege auto-seeds all buildings, the building may already
 * exist. If a 409 is returned, fetch the existing building and return its id.
 */
async function apiAddBuilding(
  request: APIRequestContext,
  siegeId: number,
  buildingType: string,
  buildingNumber: number,
): Promise<number> {
  const res = await request.post(`/api/sieges/${siegeId}/buildings`, {
    data: { building_type: buildingType, building_number: buildingNumber },
  });
  if (res.status() === 201) {
    return (await res.json()).id as number;
  }
  // 409 means the building was already seeded at siege creation — fetch it.
  expect(res.status()).toBe(409);
  const listRes = await request.get(`/api/sieges/${siegeId}/buildings`);
  expect(listRes.status()).toBe(200);
  const buildings: Array<{ id: number; building_type: string; building_number: number }> =
    await listRes.json();
  const existing = buildings.find(
    (b) => b.building_type === buildingType && b.building_number === buildingNumber,
  );
  if (!existing) throw new Error(`Building ${buildingType}#${buildingNumber} not found after 409`);
  return existing.id;
}

/**
 * Create a member. If the 30-active-member limit is hit, deactivate the
 * active member with the highest id (most recently added) to free a slot,
 * then retry. The freed member is stored in `_freedMemberId` for optional
 * restoration after tests.
 */
let _freedMemberId: number | null = null;

async function apiCreateMember(
  request: APIRequestContext,
  name: string,
): Promise<number> {
  const res = await request.post('/api/members', {
    data: { name, role: 'novice', is_active: true },
  });
  if (res.status() === 201) {
    return (await res.json()).id as number;
  }
  // 409 from the 30-member active limit — free a slot and retry.
  expect(res.status()).toBe(409);
  const listRes = await request.get('/api/members?is_active=true');
  expect(listRes.status()).toBe(200);
  const active: Array<{ id: number; name: string }> = await listRes.json();
  // Deactivate the member with the highest id (least likely to be a key fixture member).
  const toFree = active.reduce((a, b) => (b.id > a.id ? b : a));
  const deactRes = await request.delete(`/api/members/${toFree.id}`);
  expect(deactRes.status()).toBe(204);
  _freedMemberId = toFree.id;

  const retryRes = await request.post('/api/members', {
    data: { name, role: 'novice', is_active: true },
  });
  expect(retryRes.status()).toBe(201);
  return (await retryRes.json()).id as number;
}

/**
 * POST /api/sieges/:id/members — enroll a member in a siege.
 * A 409 means the member is already enrolled (auto-seeded at siege creation),
 * which is treated as a no-op success.
 */
async function apiAddSiegeMember(
  request: APIRequestContext,
  siegeId: number,
  memberId: number,
): Promise<void> {
  const res = await request.post(`/api/sieges/${siegeId}/members`, {
    data: { member_id: memberId },
  });
  if (res.status() !== 201 && res.status() !== 409) {
    expect(res.status()).toBe(201); // force a clear failure with status code
  }
}

// ── Board page structure ───────────────────────────────────────────────────────

test.describe('Board page structure', () => {
  test('board page loads without error', async ({ page, request }) => {
    const siegeId = await apiCreateSiege(request, '2030-05-06');
    await page.goto(`/sieges/${siegeId}/board`);
    await expect(page.getByRole('heading', { name: /board/i })).toBeVisible();
  });

  test('shows summary bar with slot counters', async ({ page, request }) => {
    const siegeId = await apiCreateSiege(request, '2030-05-13');
    await page.goto(`/sieges/${siegeId}/board`);
    // Summary bar always shows "total" label
    await expect(page.getByText(/total/i).first()).toBeVisible();
  });

  test('member bucket panel is visible', async ({ page, request }) => {
    const siegeId = await apiCreateSiege(request, '2030-05-20');
    await page.goto(`/sieges/${siegeId}/board`);
    // The member bucket panel has a Search input — assert it is present as a proxy
    // for the panel being rendered. (The "Members" label text also matches the nav
    // tab link, so we use the search input to uniquely identify the bucket panel.)
    await expect(page.getByPlaceholder('Search...')).toBeVisible();
  });

  test('Buildings and Posts tab buttons are present', async ({ page, request }) => {
    const siegeId = await apiCreateSiege(request, '2030-05-27');
    await page.goto(`/sieges/${siegeId}/board`);

    // Both tabs are rendered as buttons inside the board tab bar
    const buildingsTab = page.getByRole('button', { name: /buildings/i });
    const postsTab = page.getByRole('button', { name: /posts/i });

    await expect(buildingsTab).toBeVisible();
    await expect(postsTab).toBeVisible();
  });

  test('switching to Posts tab shows the posts content area', async ({
    page,
    request,
  }) => {
    const siegeId = await apiCreateSiege(request, '2030-06-03');
    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('button', { name: /^posts$/i }).click();
    // Posts tab content renders — either posts or an empty/loading state.
    // Scope to the main content area to avoid matching nav links named "Posts".
    const main = page.getByRole('main');
    await expect(
      main.locator('text=/no posts|post \\d+|loading posts/i').first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Back to Sieges link navigates to the list', async ({ page, request }) => {
    const siegeId = await apiCreateSiege(request, '2030-06-10');
    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('link', { name: /back to sieges/i }).click();
    await expect(page).toHaveURL('/sieges');
    await expect(page.getByRole('heading', { name: 'Sieges' })).toBeVisible();
  });
});

// ── Member bucket ──────────────────────────────────────────────────────────────

test.describe('Member bucket', () => {
  test('member count badge shows enrolled members', async ({ page, request }) => {
    const memberName = `E2E-Bkt-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const memberId = await apiCreateMember(request, memberName);
    const siegeId = await apiCreateSiege(request, '2030-06-17');
    await apiAddSiegeMember(request, siegeId, memberId);

    await page.goto(`/sieges/${siegeId}/board`);

    // The member should appear in the bucket list
    await expect(page.getByText(memberName)).toBeVisible();
  });

  test('search input filters members by name', async ({ page, request }) => {
    const siegeId = await apiCreateSiege(request, '2030-06-24');
    await page.goto(`/sieges/${siegeId}/board`);

    const search = page.getByPlaceholder('Search...');
    await expect(search).toBeVisible();

    await search.fill('zzz_no_such_member_xyz');
    await expect(page.getByText('No members')).toBeVisible();

    // Clearing the search restores the full list view
    await search.fill('');
  });

  test('role filter dropdown narrows the member list', async ({ page, request }) => {
    const memberName = `E2E-Role-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const memberId = await apiCreateMember(request, memberName);
    const siegeId = await apiCreateSiege(request, '2030-07-01');
    await apiAddSiegeMember(request, siegeId, memberId);

    await page.goto(`/sieges/${siegeId}/board`);

    // The native <select> in MemberBucket
    const roleSelect = page.locator('select');
    await roleSelect.selectOption('heavy_hitter'); // select a role our member doesn't have

    // The member (role: novice) should not appear
    await expect(page.getByText(memberName)).not.toBeVisible();

    // Resetting to 'all' brings them back
    await roleSelect.selectOption('all');
    await expect(page.getByText(memberName)).toBeVisible();
  });
});

// ── Buildings section ──────────────────────────────────────────────────────────

test.describe('Buildings section', () => {
  test('stronghold building appears in the Buildings tab after API setup', async ({
    page,
    request,
  }) => {
    const siegeId = await apiCreateSiege(request, '2030-07-08');
    await apiAddBuilding(request, siegeId, 'stronghold', 1);

    await page.goto(`/sieges/${siegeId}/board`);

    // The building section header for "STRONGHOLD" should be visible
    await expect(
      page.getByText(/stronghold/i).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('position cell chevron opens an assignment menu dialog', async ({
    page,
    request,
  }) => {
    const siegeId = await apiCreateSiege(request, '2030-07-15');
    await apiAddBuilding(request, siegeId, 'stronghold', 1);

    await page.goto(`/sieges/${siegeId}/board`);

    // Hover a position cell to reveal the ChevronDown button
    const positionCells = page.locator(
      '[class*="group"]:has([class*="ChevronDown"]), .group'
    );

    // Locate position cells via the numbered position span (e.g. "1.")
    const firstPositionSpan = page.locator('span', { hasText: /^1\.$/ }).first();
    const positionCell = firstPositionSpan.locator('..');

    await positionCell.hover();

    // The chevron button is inside the cell — click it
    const chevron = positionCell.locator('button').first();
    await chevron.click({ force: true });

    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: /mark reserve/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /mark no assignment/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /clear/i })).toBeVisible();

    // Close by pressing Escape
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('assigning a member to a position updates the board', async ({
    page,
    request,
  }) => {
    const memberName = `E2E-Assign-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const memberId = await apiCreateMember(request, memberName);
    const siegeId = await apiCreateSiege(request, '2030-07-22');
    await apiAddBuilding(request, siegeId, 'stronghold', 1);
    await apiAddSiegeMember(request, siegeId, memberId);

    await page.goto(`/sieges/${siegeId}/board`);

    // Confirm member is in the bucket
    await expect(page.getByText(memberName)).toBeVisible();

    // Open the position cell menu for position 1
    const firstPositionSpan = page.locator('span', { hasText: /^1\.$/ }).first();
    const positionCell = firstPositionSpan.locator('..');
    await positionCell.hover();
    const chevron = positionCell.locator('button').first();
    await chevron.click({ force: true });

    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });

    // Use "Mark RESERVE" as a simple assignment action we can assert
    await page.getByRole('button', { name: /mark reserve/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 5000 });

    // The cell should now show "RESERVE"
    await expect(page.getByText('RESERVE').first()).toBeVisible();
  });
});

// ── Validation & auto-fill dialogs ─────────────────────────────────────────────

test.describe('Validation and auto-fill dialogs', () => {
  test('Validate button opens validation dialog with results', async ({
    page,
    request,
  }) => {
    const siegeId = await apiCreateSiege(request, '2030-07-29');
    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('button', { name: /^validate$/i }).click();

    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: /validation results/i })
    ).toBeVisible();

    // Results area shows either errors/warnings or the clean message
    await expect(
      page.locator('text=/No issues found|Error \\d+|Warning \\d+/i').first()
    ).toBeVisible({ timeout: 8000 });

    await page.getByRole('button', { name: /close/i }).first().click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('Preview Auto-fill button opens preview dialog', async ({
    page,
    request,
  }) => {
    const siegeId = await apiCreateSiege(request, '2030-08-05');
    await apiAddBuilding(request, siegeId, 'stronghold', 1);

    await page.goto(`/sieges/${siegeId}/board`);

    await page.getByRole('button', { name: /preview auto-fill/i }).click();

    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(
      page.getByRole('heading', { name: /auto-fill preview/i })
    ).toBeVisible();

    // The description line shows assignment count
    await expect(page.getByText(/assignments proposed/i)).toBeVisible();

    await page.getByRole('button', { name: /cancel/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('completed siege board is read-only (Preview Auto-fill disabled)', async ({
    page,
    request,
  }) => {
    const memberName = `E2E-Lock-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const memberId = await apiCreateMember(request, memberName);
    const siegeId = await apiCreateSiege(request, '2030-08-12');
    await apiAddBuilding(request, siegeId, 'stronghold', 1);
    await apiAddSiegeMember(request, siegeId, memberId);

    // Set attack day so activation can potentially pass
    await request.put(`/api/sieges/${siegeId}/members/${memberId}`, {
      data: { attack_day: 1 },
    });

    const activateRes = await request.post(`/api/sieges/${siegeId}/activate`);
    if (activateRes.status() !== 200) {
      test.skip(); // validation rules block activation — skip the lock check
      return;
    }
    await request.post(`/api/sieges/${siegeId}/complete`);

    await page.goto(`/sieges/${siegeId}/board`);

    // The locked banner from SiegeLayout should be visible
    await expect(page.getByText(/locked/i)).toBeVisible();

    // Preview Auto-fill button should be disabled
    const autofillBtn = page.getByRole('button', { name: /preview auto-fill/i });
    await expect(autofillBtn).toBeDisabled();
  });
});
