// Foreman evidence screenshotter: capture a live app URL as photo evidence.
//   node evidence_shot.js <url> <out.png>
// Reuses the stable playwright install under /root/shots (full playwright +
// its bundled Chromium). Best-effort: a gated/slow page still yields a shot.
const { chromium } = require('/root/shots/node_modules/playwright');

const url = process.argv[2];
const out = process.argv[3];
if (!url || !out) { console.error('usage: evidence_shot.js <url> <out.png>'); process.exit(2); }

(async () => {
  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1000, height: 720 }, deviceScaleFactor: 1.3 });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: 'networkidle', timeout: 35000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.screenshot({ path: out });
  await browser.close();
  console.log('shot', out);
})().catch((e) => { console.error(String(e && e.message || e)); process.exit(1); });
