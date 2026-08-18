// Findings tally: severity chips render, the counter appears, clicking cycles
// the camera to each finding. Runs against demo/cache-diff.html.
// Usage: node tests/findings.mjs demo/cache-diff.html
import { resolve } from 'path';
const { chromium } = await import(process.env.CANVAS_TEST_PW || 'playwright');

const html = process.argv[2];
if (!html) { console.error('usage: node tests/findings.mjs <diff-canvas.html>'); process.exit(2); }
const browser = await chromium.launch({
  executablePath: process.env.CANVAS_TEST_CHROMIUM || '/opt/pw-browsers/chromium',
  args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1500, height: 900 } });
await page.goto('file://' + resolve(html));
await page.waitForTimeout(800);

const results = [];
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'} ${name}`);

check('findings counter renders', await page.isVisible('#findings'));
const tally = await page.textContent('#findings');
check('counter shows severities', /concern/.test(tally) && /nit/.test(tally));
check('severity chips on notes', (await page.$$('.note .sev')).length >= 2);
check('diff badges on cards', (await page.$$('.dbadge')).length >= 2);
check('removed lines render struck', (await page.$$('.ln.del')).length >= 2);
check('added lines render striped', (await page.$$('.ln.add')).length >= 5);

const camBefore = await page.evaluate(() => world.style.transform);
await page.click('#findings');
await page.waitForTimeout(700);
check('click jumps camera to a finding', camBefore !== await page.evaluate(() => world.style.transform));
check('target finding highlighted', await page.isVisible('.note.hot'));

console.log(results.join('\n'));
await browser.close();
process.exit(results.some(r => r.startsWith('FAIL')) ? 1 : 0);
