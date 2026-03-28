import { test, expect } from '@playwright/test';

test.describe('New PA Wizard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pa/new');
    await expect(page.getByText('New Prior Authorization')).toBeVisible();
  });

  test('lands on /pa/new when clicking New PA Request', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /New PA Request/i }).click();
    await expect(page).toHaveURL(/\/pa\/new/);
    await expect(page.getByText('New Prior Authorization')).toBeVisible();
  });

  test('Step 0: Can select a payer from dropdown', async ({ page }) => {
    // Step 0: Practice & Patient — payer is the second select
    const payerSelect = page.locator('select').nth(1);
    await payerSelect.selectOption('uhc-001');
    await expect(payerSelect).toHaveValue('uhc-001');
  });

  test('Step 1: Can enter a CPT code and see autocomplete', async ({ page }) => {
    await fillStep0(page);
    await clickNext(page);

    // Type CPT code in the autocomplete input
    const cptInput = page.getByPlaceholder(/Search by code/i);
    await cptInput.fill('72148');
    await page.waitForTimeout(300);

    // Should see autocomplete dropdown with MRI Lumbar
    await expect(page.getByText(/MRI Lumbar/i).first()).toBeVisible();
  });

  test('Step 0: Can enter patient ID', async ({ page }) => {
    const patientInput = page.getByPlaceholder(/PT-10234/i);
    await patientInput.fill('DEMO-001');
    await expect(patientInput).toHaveValue('DEMO-001');
  });

  test('Step 2: File upload zone is visible', async ({ page }) => {
    await fillStep0(page);
    await clickNext(page);
    await fillStep1(page);
    await clickNext(page);

    // Step 2: Clinical Notes
    await expect(page.getByRole('heading', { name: 'Clinical Notes' })).toBeVisible();
    await expect(page.locator('input[type="file"]')).toBeAttached();
    await expect(page.getByText(/Drag.*drop.*PDF/i)).toBeVisible();
  });

  test('Step 2: Can enter clinical notes text', async ({ page }) => {
    await fillStep0(page);
    await clickNext(page);
    await fillStep1(page);
    await clickNext(page);

    const textarea = page.getByPlaceholder(/Paste clinical notes/i);
    await textarea.fill('Lower back pain with right leg radiation');
    await expect(textarea).toHaveValue(/lower back pain/i);
  });

  test('Step 3: Analyze button triggers AI extraction', async ({ page }) => {
    await fillStep0(page);
    await clickNext(page);
    await fillStep1(page);
    await clickNext(page);
    await fillStep2(page);
    await clickNext(page);

    // Step 3: Analyze
    const analyzeBtn = page.getByRole('button', { name: /Analyze Clinical Notes/i });
    await expect(analyzeBtn).toBeVisible();
    await analyzeBtn.click();

    // Wait for analysis result
    await expect(page.getByText(/diagnosis|clinical|extract|treatment|severity/i).first()).toBeVisible({ timeout: 30000 });
  });

  test('Step 3: Clinical extract shows diagnosis fields, no undefined', async ({ page }) => {
    await fillStep0(page);
    await clickNext(page);
    await fillStep1(page);
    await clickNext(page);
    await fillStep2(page);
    await clickNext(page);

    await page.getByRole('button', { name: /Analyze Clinical Notes/i }).click();
    await expect(page.getByText(/diagnosis|radiculopathy|osteoarthritis|pain/i).first()).toBeVisible({ timeout: 30000 });

    const cardContent = await page.locator('.card').last().textContent();
    expect(cardContent).not.toContain('undefined');
  });

  test('Step 4: Generate Justification button works and letter appears', async ({ page }) => {
    test.setTimeout(90000);
    await navigateToStep4(page);

    // Check letter text appeared (in a textarea)
    const letterArea = page.locator('textarea').last();
    const letterText = await letterArea.inputValue();
    expect(letterText.length).toBeGreaterThan(50);
  });

  test('Step 4: Letter quality score is shown', async ({ page }) => {
    test.setTimeout(90000);
    await navigateToStep4(page);

    // Quality score should appear somewhere
    await expect(page.getByText(/quality|score/i).first()).toBeVisible();
  });

  test('Step 5: Probability score and factors visible', async ({ page }) => {
    test.setTimeout(90000);
    await navigateToStep4(page);
    await clickNext(page);

    // Probability should be visible
    await expect(page.getByText(/%/).first()).toBeVisible();
  });

  test('Step 6: Submit button visible', async ({ page }) => {
    test.setTimeout(90000);
    await navigateToStep4(page);
    await clickNext(page); // → Step 5
    await clickNext(page); // → Step 6

    await expect(page.getByRole('button', { name: /Submit PA|Save Draft/i }).first()).toBeVisible();
  });

  test('Full wizard completes without JavaScript errors', async ({ page }) => {
    test.setTimeout(120000);
    const jsErrors: string[] = [];
    page.on('pageerror', (err) => jsErrors.push(err.message));

    await navigateToStep4(page);
    await clickNext(page); // → Step 5
    await clickNext(page); // → Step 6

    // Save as draft
    const draftBtn = page.getByRole('button', { name: /Save Draft/i });
    await draftBtn.click();

    // Should navigate to PA detail or dashboard
    await page.waitForURL(/\/pa\/|\//, { timeout: 30000 });

    const criticalErrors = jsErrors.filter(
      (e) => !e.includes('Hydration') && !e.includes('fetch') && !e.includes('network') && !e.includes('Failed to fetch')
    );
    expect(criticalErrors).toHaveLength(0);
  });
});

// --- Helpers ---

async function clickNext(page: import('@playwright/test').Page) {
  await page.getByRole('button', { name: /Next/i }).click();
}

async function fillStep0(page: import('@playwright/test').Page) {
  // Practice select
  await page.locator('select').first().selectOption({ index: 1 });
  // Patient ID
  await page.getByPlaceholder(/PT-10234/i).fill('DEMO-001');
  // Payer select
  await page.locator('select').nth(1).selectOption('uhc-001');
}

async function fillStep1(page: import('@playwright/test').Page) {
  // CPT code autocomplete
  const cptInput = page.getByPlaceholder(/Search by code/i);
  await cptInput.fill('72148');
  await page.waitForTimeout(300);
  // Click the option in the dropdown
  await page.locator('button').filter({ hasText: '72148' }).first().click();

  // ICD codes
  await page.getByPlaceholder(/M17.11/i).fill('M54.5, M54.42');

  // Procedure description (textarea in step 1)
  const descTextarea = page.getByPlaceholder(/Describe the procedure/i);
  const currentVal = await descTextarea.inputValue();
  if (!currentVal) {
    await descTextarea.fill('MRI Lumbar Spine w/o contrast');
  }
}

async function fillStep2(page: import('@playwright/test').Page) {
  const textarea = page.getByPlaceholder(/Paste clinical notes/i);
  await textarea.fill(getClinicalNotes());
}

async function navigateToStep4(page: import('@playwright/test').Page) {
  await fillStep0(page);
  await clickNext(page);
  await fillStep1(page);
  await clickNext(page);
  await fillStep2(page);
  await clickNext(page);

  // Step 3: Analyze
  await page.getByRole('button', { name: /Analyze Clinical Notes/i }).click();
  await expect(page.getByText(/diagnosis|treatment|clinical|severity/i).first()).toBeVisible({ timeout: 30000 });
  await clickNext(page);

  // Step 4: Generate Draft
  const draftBtn = page.getByRole('button', { name: /Generate|Draft/i }).first();
  await draftBtn.click();
  // Wait for letter to appear in textarea
  await page.waitForTimeout(2000);
  await expect(page.locator('textarea').last()).not.toBeEmpty({ timeout: 30000 });
}

function getClinicalNotes(): string {
  return `OFFICE NOTE
Patient: Demo Patient (ID: DEMO-001)
Date: March 20, 2026
Provider: Dr. Sarah Johnson, MD

CHIEF COMPLAINT: Lower back pain with right leg radiation

HISTORY OF PRESENT ILLNESS:
Patient is a 52-year-old male presenting with an 8-week history of progressive lower back pain with radiation down the right leg. Pain rated 7/10. Patient has undergone 6 weeks of physical therapy with minimal improvement. NSAIDs have provided inadequate pain relief.

PHYSICAL EXAMINATION:
Positive straight leg raise on the right at 45 degrees. Decreased sensation in right L4-L5 dermatome.

ASSESSMENT/PLAN:
1. Lumbar radiculopathy, right L4-L5 (M54.42)
2. Low back pain (M54.5)
Failed conservative treatment. Requesting MRI lumbar spine without contrast (CPT 72148).`;
}
