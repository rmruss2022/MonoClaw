import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('loads at localhost:3010', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/.*localhost:300\d/);
    await expect(page.locator('h1').first()).toBeVisible();
  });

  test('shows stats: Total PAs, Approval Rate, Avg Processing Time, $ Recovered', async ({ page }) => {
    await page.goto('/');
    // Wait for stats to appear (either from API or fallback)
    await expect(page.getByText('Total PAs (this month)')).toBeVisible();
    await expect(page.getByText('Approval Rate')).toBeVisible();
    await expect(page.getByText('Avg Processing Time')).toBeVisible();
    await expect(page.getByText('$ Recovered')).toBeVisible();
  });

  test('stats have numeric values (not NaN or undefined)', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Total PAs (this month)')).toBeVisible();
    // Wait for animated count-up to finish
    await page.waitForTimeout(2000);

    // Check the page has no NaN or undefined text in stat values
    const statsSection = page.locator('.grid.grid-cols-1.gap-4');
    const statsText = await statsSection.textContent();
    expect(statsText).not.toContain('NaN');
    expect(statsText).not.toContain('undefined');

    // Check numeric content exists in each stat card
    const statCards = page.locator('.card.flex.items-center.gap-4');
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(4);
    for (let i = 0; i < count; i++) {
      const text = await statCards.nth(i).locator('.text-2xl').textContent();
      // Should contain at least one digit
      expect(text).toMatch(/\d/);
    }
  });

  test('PA list table is visible and has rows', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Recent PA Requests')).toBeVisible();
    const table = page.locator('table');
    await expect(table).toBeVisible();

    // Check header columns
    await expect(page.getByRole('columnheader', { name: /Patient ID/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /CPT Code/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /Payer/i })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: /Status/i })).toBeVisible();

    // At least 1 data row
    const rows = table.locator('tbody tr');
    await expect(rows.first()).toBeVisible();
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThanOrEqual(1);
  });

  test('"New PA Request" button is visible and clickable', async ({ page }) => {
    await page.goto('/');
    const newPaButton = page.getByRole('link', { name: /New PA Request/i });
    await expect(newPaButton).toBeVisible();
    await newPaButton.click();
    await expect(page).toHaveURL(/\/pa\/new/);
  });

  test('Navigation links work (Intelligence, Payers)', async ({ page }) => {
    await page.goto('/');

    // Click Payer Intelligence nav link
    const intelligenceLink = page.getByRole('link', { name: /Payer Intelligence/i });
    await expect(intelligenceLink).toBeVisible();
    await intelligenceLink.click();
    await expect(page).toHaveURL(/\/intelligence/);

    // Go back and click Payer Requirements
    await page.goto('/');
    const payersLink = page.getByRole('link', { name: /Payer Requirements/i });
    await expect(payersLink).toBeVisible();
    await payersLink.click();
    await expect(page).toHaveURL(/\/payers/);
  });
});
