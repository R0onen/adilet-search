/* global URL, document, console */
// Run against the production container, without MSW or scripted responses.
import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.setDefaultTimeout(30000);
page.setDefaultNavigationTimeout(30000);
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
const output = new URL('../../docs/presentation/img/final-live.png', import.meta.url);
try {
  await page.goto('http://127.0.0.1:18080', { waitUntil: 'domcontentloaded' });
  console.log('Live UI loaded.');
  await page
    .getByLabel('Ваш вопрос', { exact: true })
    .fill('Какова нормальная продолжительность рабочего времени?');
  await page.getByRole('button', { name: 'Найти ответ', exact: true }).click();
  await page.locator('.result-card').first().waitFor({ timeout: 60000 });
  const topSource = await page.locator('.result-card').first().innerText();
  console.log('Live search returned sources.');
  await page.getByRole('button', { name: 'Сформировать ответ', exact: true }).click();
  await page.locator('.answer-sources').waitFor({ timeout: 60000 });
  await page.locator('.answer-text').waitFor({ timeout: 60000 });
  await page
    .getByRole('button', { name: 'Сформировать ответ', exact: true })
    .waitFor({ timeout: 60000 });
  console.log('Generated answer completed.');
  await page.screenshot({
    path: fileURLToPath(output),
    clip: { x: 120, y: 520, width: 1200, height: 610 },
  });
  await page.locator('.result-title').first().click();
  await page.getByRole('dialog').waitFor();
  const sourceText = await page.locator('.law-text').innerText();
  if (!sourceText.includes('40')) throw new Error('Working-hours source did not contain 40');
  await page.getByRole('button', { name: 'Открыть на другом языке' }).click();
  await page.waitForFunction(() =>
    document.querySelector('.law-text')?.textContent?.includes('жұмыс'),
  );
  await page.keyboard.press('Escape');
  if (errors.length) throw new Error(errors.join('\n'));
  const report = {
    baseURL: 'http://127.0.0.1:18080',
    apiMode: 'live',
    topSource,
    sourceContains40: true,
    kazakhSwitch: true,
    pageErrors: errors,
  };
  const reportDir = new URL('../../docs/report/', import.meta.url);
  await mkdir(reportDir, { recursive: true });
  await writeFile(new URL('final_browser.json', reportDir), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
