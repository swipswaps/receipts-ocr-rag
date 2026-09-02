const { test } = require('@playwright/test');

test('Audit Live GitHub Pages for Network Errors', async ({ page }) => {
  const errors = [];
  page.on('requestfailed', req => {
    errors.push(`❌ FAILED: ${req.url()} -> ${req.failure()?.errorText}`);
  });

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`🧠 CONSOLE: ${msg.text()}`);
  });

  console.log("Navigating to Live URL...");
  await page.goto('https://swipswaps.github.io/receipts-ocr-rag/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(5000);

  // Check for the "Backend Offline" text
  const backendText = await page.locator('text=Backend').first().textContent().catch(() => 'Not found');
  console.log(`Backend Status Text: ${backendText}`);
  
  console.log("--- Errors captured ---");
  errors.forEach(e => console.log(e));

  await page.screenshot({ path: 'live-audit-failure.png', fullPage: true });
  console.log("Audit complete. Screenshot saved.");
});
