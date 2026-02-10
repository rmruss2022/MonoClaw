#!/usr/bin/env node

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const screenshots = [
  { name: 'command-hub', url: 'http://localhost:18795/hub', wait: 2000 },
  { name: 'token-tracker', url: 'http://localhost:18794', wait: 3000 },
  { name: 'monoclaw-dashboard', url: 'http://localhost:18798', wait: 3000 },
  { name: 'activity-hub', url: 'http://localhost:18796', wait: 2000 },
  { name: 'moltbook-dashboard', url: 'http://localhost:18797', wait: 2000 },
];

const outputDir = '/Users/matthew/.openclaw/workspace/MonoClaw/matts-claw-blog/public/screenshots/day3';

(async () => {
  const browser = await puppeteer.launch({ 
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  for (const screenshot of screenshots) {
    console.log(`📸 Capturing ${screenshot.name}...`);
    const page = await browser.newPage();
    await page.setViewport({ width: 1400, height: 900 });
    await page.goto(screenshot.url, { waitUntil: 'networkidle0' });
    
    // Wait for content to render
    await new Promise(resolve => setTimeout(resolve, screenshot.wait));
    
    const outputPath = path.join(outputDir, `${screenshot.name}.jpg`);
    await page.screenshot({ 
      path: outputPath,
      type: 'jpeg',
      quality: 75,
      fullPage: false
    });
    
    console.log(`  ✅ Saved to ${screenshot.name}.jpg`);
    await page.close();
  }
  
  await browser.close();
  console.log('\n🎉 All screenshots captured!');
})();
