import { test, expect } from '@playwright/test';

const API_URL = 'http://localhost:3011';

test.describe('API Health', () => {
  test('GET /api/health returns 200', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/health`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('status');
  });

  test('GET /api/payers returns 200 with array of payers', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/payers`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThanOrEqual(1);
    // Each payer should have id and name
    for (const payer of body) {
      expect(payer).toHaveProperty('id');
      expect(payer).toHaveProperty('name');
    }
  });

  test('GET /api/pa/list returns 200 with array', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/pa/list`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('POST /api/pa/analyze with sample clinical text returns clinical extract', async ({ request }) => {
    const response = await request.post(`${API_URL}/api/pa/analyze`, {
      data: {
        clinical_text: `Patient is a 52-year-old male with lumbar radiculopathy.
          Failed 6 weeks PT. Pain 7/10. Positive SLR. ICD M54.42.
          Requesting MRI lumbar spine (CPT 72148).`,
      },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('clinical_extract');
    expect(body.clinical_extract).toBeTruthy();
    // Should have some kind of diagnosis field
    const extract = body.clinical_extract;
    const extractStr = JSON.stringify(extract).toLowerCase();
    expect(extractStr).toMatch(/diagnosis|radiculopathy|lumbar|pain/);
  });

  test('GET /api/dashboard/stats returns stats object', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/dashboard/stats`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('total_this_month');
    expect(body).toHaveProperty('approval_rate');
    expect(body).toHaveProperty('avg_processing_days');
    expect(body).toHaveProperty('revenue_recovered');
    expect(typeof body.total_this_month).toBe('number');
  });

  test('GET /api/payers/requirements returns array', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/payers/requirements`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/dashboard/appeal-stats returns appeal data', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/dashboard/appeal-stats`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('most_winnable');
    expect(Array.isArray(body.most_winnable)).toBe(true);
  });

  test('GET /api/dashboard/activity-feed returns array', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/dashboard/activity-feed`);
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('POST /api/pa/create creates a new PA', async ({ request }) => {
    // First get payers and practices
    const payersRes = await request.get(`${API_URL}/api/payers`);
    const payers = await payersRes.json();
    const practicesRes = await request.get(`${API_URL}/api/practices`);
    const practices = await practicesRes.json();

    const response = await request.post(`${API_URL}/api/pa/create`, {
      data: {
        practice_id: practices[0]?.id || 'practice-001',
        payer_id: payers[0]?.id || 'payer-001',
        patient_id: 'TEST-API-001',
        cpt_code: '72148',
        icd10_codes: ['M54.5'],
      },
    });
    expect(response.status()).toBe(201);
    const body = await response.json();
    expect(body).toHaveProperty('id');
    expect(body.status).toBe('draft');
  });

  test('POST /api/pa/draft returns justification letter', async ({ request }) => {
    // Get a real payer ID from the DB
    const payersRes = await request.get(`${API_URL}/api/payers`);
    const payers = await payersRes.json();
    const uhc = payers.find((p: any) => p.name.includes('United')) || payers[0];

    const response = await request.post(`${API_URL}/api/pa/draft`, {
      data: {
        clinical_extract: {
          primary_diagnosis: 'Lumbar radiculopathy',
          severity: '7/10 pain',
          prior_treatments: [
            { treatment: 'Physical therapy', duration: '6 weeks', outcome: 'minimal improvement' },
            { treatment: 'NSAIDs', duration: '8 weeks', outcome: 'inadequate relief' },
          ],
          symptoms: ['lower back pain', 'right leg radiation'],
          duration_weeks: 8,
        },
        cpt_code: '72148',
        payer_id: uhc.id,
      },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('justification');
    expect(body.justification.length).toBeGreaterThan(100);
    expect(body).toHaveProperty('probability');
    expect(body.probability).toHaveProperty('probability');
  });
});
