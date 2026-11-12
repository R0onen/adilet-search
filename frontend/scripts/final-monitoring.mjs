/* global URL, console */
import { chromium } from '@playwright/test';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const env = await readFile(new URL('../../.env.final', import.meta.url), 'utf8');
const password = env.match(/^GRAFANA_ADMIN_PASSWORD=(.+)$/m)?.[1].trim();
if (!password) throw new Error('Missing Grafana password in ignored .env.final');
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto('http://127.0.0.1:13000/login');
  await page.getByPlaceholder('email or username').fill('admin');
  await page.getByPlaceholder('password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Log in', exact: true }).click();
  await page.waitForURL((url) => !url.pathname.endsWith('/login'));
  await page.goto('http://127.0.0.1:13000/d/adilet-final');
  await page.getByText('Service availability', { exact: true }).waitFor();
  // Wait for the provisioned Prometheus datasource to return actual samples.
  const targets = await page.request.get('http://127.0.0.1:19090/api/v1/targets');
  const body = await targets.json();
  const health = body.data.activeTargets.map((t) => ({ job: t.labels.job, health: t.health }));
  if (health.length !== 2 || health.some((t) => t.health !== 'up')) {
    throw new Error('Monitoring targets are not both up');
  }
  await page.screenshot({
    path: fileURLToPath(
      new URL('../../docs/presentation/img/final-monitoring.png', import.meta.url),
    ),
    fullPage: true,
  });
  await writeFile(
    new URL('../../docs/report/final_monitoring.json', import.meta.url),
    JSON.stringify({ targets: health, grafanaDashboard: 'adilet-final' }, null, 2) + '\n',
  );
  console.log('Grafana dashboard loaded; both Prometheus targets are up.');
} finally {
  await browser.close();
}
