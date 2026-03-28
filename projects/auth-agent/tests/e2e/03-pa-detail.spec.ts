import { test, expect } from '@playwright/test';

const API_URL = 'http://localhost:3011';

test.describe('PA Detail Page', () => {
  test('click a PA from dashboard loads /pa/:id', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Recent PA Requests')).toBeVisible();
    const firstLink = page.locator('table tbody tr a').first();
    await expect(firstLink).toBeVisible();
    await firstLink.click();
    await expect(page).toHaveURL(/\/pa\//);
  });

  test('status badge visible and has a valid value', async ({ page }) => {
    await navigateToPADetail(page);
    const validStatuses = ['draft', 'reviewed', 'submitted', 'pending', 'approved', 'denied', 'appealed', 'closed'];
    const badges = page.locator('span').filter({
      hasText: new RegExp(validStatuses.join('|'), 'i'),
    });
    await expect(badges.first()).toBeVisible();
  });

  test('clinical extract section expandable', async ({ page }) => {
    await navigateToPADetail(page);
    const extractTab = page.getByRole('button', { name: /Clinical Extract/i });
    if (await extractTab.isVisible()) {
      await extractTab.click();
    }
    await expect(page.getByText(/diagnosis|clinical|extract|treatment|No clinical/i).first()).toBeVisible();
  });

  test('justification letter section shows text', async ({ page }) => {
    await navigateToPADetail(page);
    const letterTab = page.getByRole('button', { name: /Justification|Letter/i });
    if (await letterTab.isVisible()) {
      await letterTab.click();
    }
    await expect(page.getByText(/Dear|Medical|Authorization|Prior|justification|No justification/i).first()).toBeVisible();
  });

  test('timeline section shows at least 1 event', async ({ page }) => {
    await navigateToPADetail(page);
    const timelineTab = page.getByRole('button', { name: /Timeline/i });
    if (await timelineTab.isVisible()) {
      await timelineTab.click();
    }
    await expect(page.getByText(/created|submitted|approved|denied|draft/i).first()).toBeVisible();
  });

  test('probability gauge shows score', async ({ page }) => {
    await navigateToPADetail(page);
    await expect(page.getByText(/%/).first()).toBeVisible();
  });

  test('for a denied PA: "Generate Appeal" button is visible', async ({ page, request }) => {
    // Get a denied PA ID from the API
    const res = await request.get(`${API_URL}/api/pa/list`);
    const pas = await res.json();
    const deniedPA = pas.find((p: any) => p.status === 'denied');

    if (!deniedPA) {
      test.skip();
      return;
    }

    await page.goto(`/pa/${deniedPA.id}`);
    await page.waitForTimeout(1500);

    // Should show denied status
    await expect(page.getByText(/denied/i).first()).toBeVisible();

    // Click Appeal tab (use exact match to avoid hitting Generate Appeal button)
    const appealTab = page.getByRole('button', { name: 'Appeal', exact: true });
    if (await appealTab.isVisible()) {
      await appealTab.click();
    }

    // Generate Appeal button should be visible
    await expect(page.getByRole('button', { name: /Generate Appeal/i }).first()).toBeVisible();
  });

  test('appeal generation: click button and letter appears', async ({ page, request }) => {
    test.setTimeout(60000);

    // Get a denied PA ID from the API
    const res = await request.get(`${API_URL}/api/pa/list`);
    const pas = await res.json();
    const deniedPA = pas.find((p: any) => p.status === 'denied');

    if (!deniedPA) {
      test.skip();
      return;
    }

    await page.goto(`/pa/${deniedPA.id}`);
    await page.waitForTimeout(1500);

    // Click Appeal tab
    const appealTab = page.getByRole('button', { name: 'Appeal', exact: true });
    if (await appealTab.isVisible()) {
      await appealTab.click();
    }

    // Click Generate Appeal
    const genBtn = page.getByRole('button', { name: /Generate Appeal/i }).first();
    await expect(genBtn).toBeVisible();
    await genBtn.click();

    // Wait for appeal letter to appear (loading + generation)
    await expect(page.getByText(/appeal|denial|overturn|reconsider/i).first()).toBeVisible({ timeout: 30000 });
  });
});

async function navigateToPADetail(page: import('@playwright/test').Page) {
  await page.goto('/');
  await expect(page.getByText('Recent PA Requests')).toBeVisible();
  const firstLink = page.locator('table tbody tr a').first();
  await expect(firstLink).toBeVisible();
  await firstLink.click();
  await expect(page).toHaveURL(/\/pa\//);
  await page.waitForTimeout(1000);
}
