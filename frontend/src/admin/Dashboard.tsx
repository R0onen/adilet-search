import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import * as api from '../api/admin';
import { BarList, LineChart } from './charts';
import { lastDays, latencyTone, milliseconds, percent } from './format';
import type { Tone } from './format';

const LANG_LABELS: Record<string, string> = { ru: 'Русский', kk: 'Қазақша' };
const MODE_LABELS: Record<string, string> = {
  hybrid: 'Гибридный',
  semantic: 'Семантический',
  keyword: 'По ключевым словам',
};

function Tile({
  label,
  value,
  hint,
  tone = 'neutral',
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
}) {
  return (
    <div className={`kpi-tile tone-${tone}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  );
}

function QueryTable({
  title,
  rows,
  range,
  zeroOnly = false,
}: {
  title: string;
  rows: api.Stats['top_queries'];
  range: { from: string; to: string };
  zeroOnly?: boolean;
}) {
  return (
    <div className="admin-card">
      <h2>{title}</h2>
      {rows.length === 0 ? (
        <p className="admin-empty">Нет запросов за период</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Запрос</th>
              <th className="numeric">Раз</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const params = new URLSearchParams({
                q: row.query,
                date_from: range.from,
                date_to: range.to,
              });
              if (zeroOnly) params.set('zero_results', 'true');
              return (
                <tr key={row.query}>
                  <td>
                    <Link to={`/admin/queries?${params.toString()}`}>{row.query}</Link>
                  </td>
                  <td className="numeric">{row.count}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [params, setParams] = useSearchParams();
  const preset = params.get('range') || '7';
  const custom = preset === 'custom';
  const range = custom
    ? { from: params.get('from') || lastDays(7).from, to: params.get('to') || lastDays(7).to }
    : lastDays(Number(preset) || 7);
  const stats = useQuery({
    queryKey: ['admin', 'stats', range.from, range.to],
    queryFn: ({ signal }) => api.stats(range.from, range.to, signal),
  });
  const data = stats.data;
  return (
    <>
      <div className="admin-toolbar">
        <h1>Статистика</h1>
        <div className="segmented" role="group" aria-label="Период">
          {[
            ['7', '7 дней'],
            ['30', '30 дней'],
            ['custom', 'Свой период'],
          ].map(([value, label]) => (
            <button
              key={value}
              aria-pressed={preset === value}
              onClick={() =>
                setParams(
                  value === 'custom'
                    ? { range: 'custom', from: range.from, to: range.to }
                    : { range: value },
                )
              }
            >
              {label}
            </button>
          ))}
        </div>
        {custom && (
          <div className="date-range">
            <label>
              с
              <input
                type="date"
                value={range.from}
                max={range.to}
                onChange={(event) =>
                  setParams({ range: 'custom', from: event.target.value, to: range.to })
                }
              />
            </label>
            <label>
              по
              <input
                type="date"
                value={range.to}
                min={range.from}
                onChange={(event) =>
                  setParams({ range: 'custom', from: range.from, to: event.target.value })
                }
              />
            </label>
          </div>
        )}
      </div>
      {stats.isError && (
        <div role="alert" className="error-box">
          <p>Не удалось загрузить статистику: {stats.error.message}</p>
        </div>
      )}
      {stats.isPending && <div className="skeleton-block" />}
      {data && (
        <>
          <p className="admin-note">
            {data.date_from} — {data.date_to}, дни по UTC
          </p>
          <div className="kpi-grid">
            <Tile label="Запросов" value={String(data.totals.queries)} />
            <Tile label="Уникальных сессий" value={String(data.totals.unique_sessions)} />
            <Tile label="Ответов ИИ" value={String(data.totals.answers)} />
            <Tile
              label="Поиск, p95"
              value={milliseconds(data.latency_ms.search_p95)}
              hint={`цель ≤ 2 с · p50 ${milliseconds(data.latency_ms.search_p50)}`}
              tone={latencyTone(data.latency_ms.search_p95)}
            />
            <Tile
              label="Без результатов"
              value={percent(data.rates.zero_result_rate)}
              hint={`${data.totals.zero_result_queries} запросов`}
            />
            <Tile
              label="Удовлетворённость"
              value={percent(data.rates.satisfaction_rate)}
              hint={`👍 ${data.totals.feedback_positive} · 👎 ${data.totals.feedback_negative}`}
            />
            <Tile
              label="Деградация"
              value={percent(data.rates.degraded_rate)}
              hint="ответы в упрощённом режиме"
            />
            <Tile
              label="Первый токен ответа, p95"
              value={milliseconds(data.latency_ms.answer_ttft_p95)}
              hint={`p50 ${milliseconds(data.latency_ms.answer_ttft_p50)}`}
            />
          </div>
          <div className="admin-grid">
            <div className="admin-card">
              <h2>Запросы по дням</h2>
              <LineChart
                title="Запросы по дням"
                points={data.by_day.map((day) => ({ label: day.date, value: day.queries }))}
              />
            </div>
            <div className="admin-card">
              <h2>Время поиска p95 по дням, мс</h2>
              <LineChart
                title="Время поиска p95 по дням"
                unit=" мс"
                points={data.by_day.map((day) => ({
                  label: day.date,
                  value: day.search_p95_ms ?? null,
                }))}
                reference={{ value: 2000, label: 'цель 2000 мс' }}
              />
            </div>
            <div className="admin-card">
              <h2>Языки запросов</h2>
              <BarList
                title="Языки запросов"
                items={data.by_lang.map((row) => ({
                  label: LANG_LABELS[row.lang] ?? row.lang,
                  value: row.queries,
                }))}
              />
            </div>
            <div className="admin-card">
              <h2>Режимы поиска</h2>
              <BarList
                title="Режимы поиска"
                items={data.by_mode.map((row) => ({
                  label: MODE_LABELS[row.mode] ?? row.mode,
                  value: row.queries,
                }))}
              />
            </div>
            <QueryTable title="Частые запросы" rows={data.top_queries} range={range} />
            <QueryTable
              title="Пробелы в базе / непонятые запросы"
              rows={data.top_zero_result_queries}
              range={range}
              zeroOnly
            />
          </div>
        </>
      )}
    </>
  );
}
