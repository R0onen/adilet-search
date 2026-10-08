import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('presentation journey: search, streamed citations, article translation, compare', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Право, понятным языком.' })).toBeVisible();
  await page.screenshot({ path: '../docs/presentation/img/frontend-home.png', fullPage: true });
  await page.getByRole('button', { name: 'Мне не платят зарплату' }).click();
  await expect(page.locator('.result-card')).toHaveCount(2);
  await page.getByRole('button', { name: 'Сформировать ответ' }).click();
  await expect(page.locator('.citation').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Сформировать ответ' })).toBeVisible({
    timeout: 15000,
  });
  await page.locator('.citation').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('.law-text')).toContainText('За задержку выплаты');
  await page.getByRole('button', { name: 'Открыть на другом языке' }).click();
  await expect(page.locator('.law-text')).toContainText('Жалақыны');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.map((item) => ({
      id: item.id,
      nodes: item.nodes.map((node) => node.target),
    })),
  ).toEqual([]);
  await page.screenshot({ path: '../docs/presentation/img/frontend-results.png', fullPage: true });
  await page.getByRole('link', { name: 'Сравнение' }).click();
  await page.getByRole('button', { name: 'Мне не платят зарплату' }).click();
  await expect(page.locator('.compare-grid')).toBeVisible();
  await expect(page.locator('.smart-column .result-card')).toHaveCount(2);
  await page.screenshot({ path: '../docs/presentation/img/frontend-compare.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('empty results, simulated errors, and keyboard-accessible home', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#question')).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.getByLabel('Ваш вопрос', { exact: true }).fill('астрономия галактика');
  await page.getByRole('button', { name: 'Найти ответ' }).click();
  await expect(
    page.getByRole('heading', { name: 'Подходящих источников не найдено' }),
  ).toBeVisible();
  await page.getByLabel('Ваш вопрос', { exact: true }).fill('/error');
  await page.getByRole('button', { name: 'Найти ответ' }).click();
  await expect(page.getByRole('alert')).toContainText('Simulated service failure');
});

test('360px layout and Kazakh search', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto('/');
  await page.getByRole('button', { name: 'ҚАЗ', exact: true }).click();
  await page.getByRole('button', { name: 'Жалақымды төлемейді' }).click();
  await expect(page.locator('.result-card').first()).toContainText('Жалақыны');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: '../docs/presentation/img/frontend-mobile.png', fullPage: true });
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});

test('answer cancellation and backend failures preserve retrieved sources', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Мне не платят зарплату' }).click();
  await page.getByRole('button', { name: 'Сформировать ответ' }).click();
  await expect(page.locator('.citation').first()).toBeVisible();
  await page.getByRole('button', { name: 'Остановить', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Генерация остановлена');
  await expect(page.locator('.result-card')).toHaveCount(2);
  for (const suffix of ['/answer-error', '/stream-error']) {
    await page.getByLabel('Ваш вопрос', { exact: true }).fill(`Мне не платят зарплату ${suffix}`);
    await page.getByRole('button', { name: 'Найти ответ' }).click();
    await page.getByRole('button', { name: 'Сформировать ответ' }).click();
    await expect(page.getByRole('alert')).toContainText('AI-ответ недоступен');
    await expect(page.locator('.result-card')).toHaveCount(2);
    await page.locator('.result-title').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
  }
});
