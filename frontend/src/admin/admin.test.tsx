import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { setupServer } from 'msw/node';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { storeToken } from '../api/admin';
import { MOCK_TOKEN, ZERO_QUERY, adminHandlers } from '../mocks/admin';
import AdminApp from './AdminApp';
import { compact, lastDays, latencyTone, milliseconds, percent } from './format';

const server = setupServer(...adminHandlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  storeToken(null);
});
afterAll(() => server.close());

function Where() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}
function renderAdmin(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/admin/*" element={<AdminApp />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const where = () => screen.getByTestId('location').textContent;

describe('admin helpers', () => {
  it('colours the search p95 against the 2 s target', () => {
    expect(latencyTone(900)).toBe('good');
    expect(latencyTone(1500)).toBe('good');
    expect(latencyTone(1501)).toBe('warn');
    expect(latencyTone(2000)).toBe('warn');
    expect(latencyTone(2001)).toBe('bad');
    expect(latencyTone(null)).toBe('neutral');
  });
  it('formats rates, durations and date ranges', () => {
    expect(percent(0.838)).toBe('83.8%');
    expect(percent(null)).toBe('—');
    expect(milliseconds(910)).toBe('910 мс');
    expect(milliseconds(2100)).toBe('2.10 с');
    expect(milliseconds(undefined)).toBe('—');
    expect(lastDays(7, new Date('2026-11-07T15:00:00Z'))).toEqual({
      from: '2026-11-01',
      to: '2026-11-07',
    });
    expect(compact({ q: 'x', lang: '', mode: undefined })).toEqual({ q: 'x' });
  });
});

describe('admin auth', () => {
  it('sends an anonymous visitor to the login page and back after login', async () => {
    const user = userEvent.setup();
    renderAdmin('/admin/queries?lang=kk');
    expect(await screen.findByRole('heading', { name: 'Вход для администратора' })).toBeVisible();
    expect(where()).toBe('/admin/login');

    await user.click(screen.getByRole('button', { name: 'Войти' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Введите логин и пароль');

    await user.type(screen.getByLabelText('Логин'), 'admin');
    await user.type(screen.getByLabelText('Пароль'), 'wrong');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Неверный логин или пароль');

    await user.clear(screen.getByLabelText('Пароль'));
    await user.type(screen.getByLabelText('Пароль'), 'demo');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    // back on the page that was asked for, with its filter
    expect(await screen.findByRole('heading', { name: 'Журнал запросов' })).toBeVisible();
    expect(where()).toBe('/admin/queries?lang=kk');
    expect(sessionStorage.getItem('adilet_admin_token')).toBe(MOCK_TOKEN);
  });

  it('shows the wait time when login is rate limited', async () => {
    const user = userEvent.setup();
    renderAdmin('/admin/login');
    await user.type(await screen.findByLabelText('Логин'), 'limited');
    await user.type(screen.getByLabelText('Пароль'), 'x');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Повторите через 42 с');
  });

  it('logs out when the server rejects the token', async () => {
    storeToken('expired-token');
    renderAdmin('/admin');
    expect(await screen.findByRole('heading', { name: 'Вход для администратора' })).toBeVisible();
    expect(sessionStorage.getItem('adilet_admin_token')).toBeNull();
  });

  it('logs out on request', async () => {
    const user = userEvent.setup();
    storeToken(MOCK_TOKEN);
    renderAdmin('/admin');
    await user.click(await screen.findByRole('button', { name: /Выйти/ }));
    expect(await screen.findByRole('heading', { name: 'Вход для администратора' })).toBeVisible();
    expect(sessionStorage.getItem('adilet_admin_token')).toBeNull();
  });
});

describe('admin pages', () => {
  it('goes from the dashboard to the filtered log and opens a query', async () => {
    const user = userEvent.setup();
    storeToken(MOCK_TOKEN);
    renderAdmin('/admin');

    expect(await screen.findByText('1240')).toBeVisible(); // total queries
    expect(screen.getByText('910 мс')).toBeVisible(); // search p95
    expect(screen.getByText('83.8%')).toBeVisible(); // satisfaction
    const gaps = screen.getByRole('heading', { name: 'Пробелы в базе / непонятые запросы' });
    await user.click(within(gaps.parentElement!).getByRole('link', { name: ZERO_QUERY }));

    // the click carried the query and the zero-results filter into the URL
    expect(await screen.findByRole('heading', { name: 'Журнал запросов' })).toBeVisible();
    expect(where()).toContain('zero_results=true');
    expect(where()).toContain(`q=${encodeURIComponent(ZERO_QUERY).replace(/%20/g, '+')}`);
    await waitFor(() => expect(screen.getByText('Найдено: 2')).toBeVisible());
    expect(screen.getByLabelText('без результатов')).toBeChecked();

    // filters are URL-synced: unticking removes the parameter and widens the list
    await user.click(screen.getByLabelText('без результатов'));
    expect(where()).not.toContain('zero_results');
    await user.click(screen.getByRole('button', { name: 'Сбросить фильтры' }));
    await waitFor(() => expect(screen.getByText('Найдено: 5')).toBeVisible());

    await user.click(screen.getByRole('button', { name: 'Мне не платят зарплату' }));
    expect(where()).toContain('open=00000000-0000-4000-8000-000000000001');
    const drawer = await screen.findByRole('dialog');
    expect(
      await within(drawer).findByText(/Тестовый ТК · Ответственность работодателя/),
    ).toBeVisible();
    expect(within(drawer).getByText(/реранкинг: 312 мс/)).toBeVisible();
    expect(within(drawer).getByText(/за задержку заработной платы \[1\]/)).toBeVisible();
    expect(within(drawer).getByText(/опирается на источники/)).toBeVisible();
  });

  it('runs a reindex with progress and reports a conflict', async () => {
    const user = userEvent.setup();
    storeToken(MOCK_TOKEN);
    renderAdmin('/admin/system');

    expect(await screen.findByText('ML-сервис')).toBeVisible();
    expect(screen.getByText('не настроен')).toBeVisible(); // the LLM in the mock
    expect(screen.getByText('legal_chunks → legal_chunks__demo')).toBeVisible();

    await user.click(screen.getByRole('button', { name: /Переиндексировать/ }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Поиск продолжает работать на старом индексе/)).toBeVisible();
    await user.selectOptions(within(dialog).getByLabelText('Корпус'), 'sample');
    await user.click(within(dialog).getByRole('button', { name: 'Запустить' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'Переиндексация уже выполняется',
    );

    await user.selectOptions(within(dialog).getByLabelText('Корпус'), 'processed');
    await user.click(within(dialog).getByRole('button', { name: 'Запустить' }));
    expect(await screen.findByText(/Переиндексация: выполняется/)).toBeVisible();
    expect(
      await screen.findByText(/Переиндексация: завершена/, {}, { timeout: 9000 }),
    ).toBeVisible();
    expect(screen.getByText(/100%/)).toBeVisible();
  }, 15000);
});
