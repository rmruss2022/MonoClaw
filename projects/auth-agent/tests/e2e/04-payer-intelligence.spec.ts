import { test, expect } from '@playwright/test';

test.describe('Payer Intelligence', () => {
  test('/intelligence page loads', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByRole('heading', { name: 'Payer Intelligence' })).toBeVisible();
  });

  test('shows denial rate stats by payer', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByText('Denial Rates by Payer')).toBeVisible();

    // Should show payer names
    await expect(page.getByText('Aetna').first()).toBeVisible();
    await expect(page.getByText('UnitedHealth').first()).toBeVisible();
  });

  test('shows win rate by CARC code', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByText(/Most Winnable Denials/i)).toBeVisible();

    // Should show CARC codes
    await expect(page.getByText('CO-50').first()).toBeVisible();
    await expect(page.getByText('CO-16').first()).toBeVisible();
  });

  test('charts render without errors (no blank canvases)', async ({ page }) => {
    await page.goto('/intelligence');
    await page.waitForTimeout(2000);

    // The denial rate chart should have rendered SVG elements
    const svgElements = page.locator('.recharts-wrapper svg');
    const svgCount = await svgElements.count();
    expect(svgCount).toBeGreaterThanOrEqual(1);

    // Check no JS errors during rendering
    const jsErrors: string[] = [];
    page.on('pageerror', (err) => jsErrors.push(err.message));
    await page.waitForTimeout(1000);

    const criticalErrors = jsErrors.filter(
      (e) => !e.includes('Hydration') && !e.includes('fetch')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('shows payer-specific tips', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByText(/Payer-Specific Tips/i)).toBeVisible();

    // Should show tips for at least some payers
    await expect(page.getByText(/conservative treatment/i).first()).toBeVisible();
  });

  test('denial rate matrix shows payer x CPT breakdown', async ({ page }) => {
    await page.goto('/intelligence');
    await expect(page.getByText(/Payer.*CPT.*Denial Rate Matrix/i)).toBeVisible();

    // Should show Overall column and CPT columns
    await expect(page.getByText('Overall').first()).toBeVisible();
  });
});
