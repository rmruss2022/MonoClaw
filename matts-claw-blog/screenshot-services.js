#!/usr/bin/env node
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });
  await page.goto('http://localhost:18802/hub', { waitUntil: 'networkidle0', timeout: 10000 });
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Find the services card and screenshot just that section
  const servicesCard = await page.$('.card:nth-child(2)');
  if (servicesCard) {
    await servicesCard.screenshot({ 
      path: 'public/screenshots/services-grid.jpg',
      type: 'jpeg',
      quality: 80
    });
    console.log('✓ Services grid screenshot captured');
  } else {
    console.log('✗ Services card not found, taking full page screenshot');
    await page.screenshot({ 
      path: 'public/screenshots/services-grid.jpg',
      fullPage: false,
      type: 'jpeg',
      quality: 80
    });
  }
  
  await browser.close();
})();
