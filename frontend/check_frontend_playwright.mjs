import { chromium, firefox } from '@playwright/test';

async function run(name, browserType) {
  let browser;
  try {
    browser = await browserType.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}\n${err.stack || ''}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`console:${msg.type()}: ${msg.text()}`);
    });
    await page.goto('http://127.0.0.1:5173/', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);
    const body = await page.locator('body').innerText().catch(() => '');
    const rootText = await page.locator('#root').innerText().catch(() => '');
    console.log(`=== ${name} ===`);
    console.log('title:', await page.title());
    console.log('body:', body.slice(0, 500));
    console.log('root:', rootText.slice(0, 500));
    console.log('errors:', errors.length ? errors.join('\n---\n') : 'none');
  } catch (error) {
    console.log(`=== ${name} FAILED ===`);
    console.log(String(error));
  } finally {
    if (browser) await browser.close();
  }
}

await run('chromium', chromium);
await run('firefox', firefox);
