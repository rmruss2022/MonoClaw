import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: { timeout: 15000 },
  retries: 0,
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'npm run dev:api',
      port: 3011,
      reuseExistingServer: true,
      timeout: 30000,
    },
    {
      command: 'npm run dev:ui',
      port: 3000,
      reuseExistingServer: true,
      timeout: 30000,
    },
  ],
});
