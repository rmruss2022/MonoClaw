#!/usr/bin/env node

const puppeteer = require('puppeteer');
const fs = require('fs').promises;
const path = require('path');

const dashboards = [
  { name: 'command-hub', url: 'http://localhost:18795/hub', title: 'Command Hub' },
  { name: 'token-tracker', url: 'http://localhost:18794', title: 'Token Usage Tracker' },
  { name: 'raves-dashboard', url: 'http://localhost:18793', title: 'Raves Dashboard' },
  { name: 'job-dashboard', url: 'http://localhost:18792', title: 'Job Dashboard' }
];

async function takeScreenshots() {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const outputDir = path.join(__dirname, 'public', 'screenshots');
  await fs.mkdir(outputDir, { recursive: true });

  for (const dashboard of dashboards) {
    try {
      console.log(`Taking screenshot of ${dashboard.title}...`);
      const page = await browser.newPage();
      await page.setViewport({ width: 1280, height: 800 });
      await page.goto(dashboard.url, { waitUntil: 'networkidle0', timeout: 10000 });
      
      // Wait a bit for any animations/charts to load
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const screenshotPath = path.join(outputDir, `${dashboard.name}.jpg`);
      await page.screenshot({ 
        path: screenshotPath, 
        fullPage: true,
        type: 'jpeg',
        quality: 80
      });
      console.log(`✓ Saved ${dashboard.name}.jpg`);
      
      await page.close();
    } catch (error) {
      console.error(`✗ Failed to screenshot ${dashboard.title}:`, error.message);
    }
  }

  await browser.close();
  console.log('\n✓ All screenshots completed!');
}

takeScreenshots().catch(console.error);
