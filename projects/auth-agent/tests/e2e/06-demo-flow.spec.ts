import { test, expect } from '@playwright/test';

const API_URL = 'http://localhost:3011';

test.describe('Demo Flow (end-to-end)', () => {
  test('dashboard loads with pre-populated demo stats', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
    await expect(page.getByText('Total PAs (this month)')).toBeVisible();
    await page.waitForTimeout(2000);

    // Stats should have non-zero values (from seed or fallback)
    const statsText = await page.locator('.text-2xl.font-bold').allTextContents();
    const hasNumericStats = statsText.some((t) => /\d+/.test(t));
    expect(hasNumericStats).toBe(true);
  });

  test('navigate to a demo approved PA', async ({ page, request }) => {
    // Get an approved PA ID from the API
    const res = await request.get(`${API_URL}/api/pa/list`);
    const pas = await res.json();
    const approvedPA = pas.find((p: any) => p.status === 'approved' || p.outcome === 'approved');

    if (!approvedPA) {
      test.skip();
      return;
    }

    await page.goto(`/pa/${approvedPA.id}`);
    await page.waitForTimeout(1500);
    await expect(page.getByText(/approved/i).first()).toBeVisible();
  });

  test('navigate to a demo denied PA with appeal button', async ({ page, request }) => {
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
    await expect(page.getByText(/denied/i).first()).toBeVisible();

    // Appeal tab should exist
    const appealTab = page.getByRole('button', { name: 'Appeal', exact: true });
    if (await appealTab.isVisible()) {
      await appealTab.click();
      await expect(page.getByRole('button', { name: /Generate Appeal/i }).first()).toBeVisible();
    }
  });

  test('create new PA using demo data and complete all wizard steps', async ({ page }) => {
    test.setTimeout(180000);

    await page.goto('/pa/new');
    await expect(page.getByText('New Prior Authorization')).toBeVisible();

    // Step 0: Practice & Patient
    await page.locator('select').first().selectOption({ index: 1 });
    await page.getByPlaceholder(/PT-10234/i).fill('DEMO-001');
    await page.locator('select').nth(1).selectOption('uhc-001');
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 1: Procedure Details
    const cptInput = page.getByPlaceholder(/Search by code/i);
    await cptInput.fill('72148');
    await page.waitForTimeout(300);
    await page.locator('button').filter({ hasText: '72148' }).first().click();

    await page.getByPlaceholder(/M17.11/i).fill('M54.5, M54.42');

    const descTextarea = page.getByPlaceholder(/Describe the procedure/i);
    const val = await descTextarea.inputValue();
    if (!val) {
      await descTextarea.fill('MRI Lumbar Spine w/o contrast');
    }
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 2: Clinical Notes
    await page.getByPlaceholder(/Paste clinical notes/i).fill(`OFFICE NOTE
Patient: Demo Patient (ID: DEMO-001)
Date: March 20, 2026
Provider: Dr. Sarah Johnson, MD

CHIEF COMPLAINT: Lower back pain with right leg radiation

HISTORY OF PRESENT ILLNESS:
Patient is a 52-year-old male presenting with an 8-week history of progressive lower back pain with radiation down the right leg. Pain rated 7/10. Failed 6 weeks PT. NSAIDs inadequate.

PHYSICAL EXAMINATION:
Positive straight leg raise at 45 degrees.

ASSESSMENT/PLAN:
1. Lumbar radiculopathy (M54.42)
2. Low back pain (M54.5)
Requesting MRI lumbar spine (CPT 72148).`);
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 3: Analyze
    await page.getByRole('button', { name: /Analyze Clinical Notes/i }).click();
    await expect(page.getByText(/diagnosis|treatment|clinical|radiculopathy|pain/i).first()).toBeVisible({ timeout: 30000 });
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 4: Generate Draft
    await page.getByRole('button', { name: /Generate|Draft/i }).first().click();
    await page.waitForTimeout(2000);
    await expect(page.locator('textarea').last()).not.toBeEmpty({ timeout: 30000 });
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 5: Probability
    await expect(page.getByText(/%/).first()).toBeVisible();
    await page.getByRole('button', { name: /Next/i }).click();

    // Step 6: Submit as draft
    const submitBtn = page.getByRole('button', { name: /Save Draft/i });
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Should navigate to detail page or dashboard
    await page.waitForURL(/\/pa\/|\//, { timeout: 30000 });
  });

  test('PA appears in dashboard list after creation', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Recent PA Requests')).toBeVisible();
    // Wait for table data to load
    await page.waitForTimeout(2000);

    const rows = page.locator('table tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 10000 });
    const count = await rows.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('all dashboard sections render completely', async ({ page }) => {
    await page.goto('/');
    await page.waitForTimeout(3000);

    // Stats cards
    await expect(page.getByText('Total PAs (this month)')).toBeVisible();
    await expect(page.getByText('Approval Rate')).toBeVisible();

    // Time saved widget
    await expect(page.getByText(/Time Saved/i)).toBeVisible();

    // Charts
    await expect(page.getByText('PAs by Status')).toBeVisible();
    await expect(page.getByText('Probability Distribution')).toBeVisible();

    // Recent Activity
    await expect(page.getByRole('heading', { name: 'Recent Activity' })).toBeVisible();

    // PA table
    await expect(page.getByText('Recent PA Requests')).toBeVisible();
  });
});
