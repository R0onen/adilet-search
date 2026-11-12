import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Download, X } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import * as api from '../api/admin';
import { Button } from '../components/ui/button';
import { TimingBar } from './charts';
import { DEGRADED_LABELS, compact, dateTime, milliseconds } from './format';

const PAGE_SIZE = 20;
const FILTER_KEYS = [
  'q',
  'lang',
  'mode',
  'zero_results',
  'feedback',
  'degraded',
  'date_from',
  'date_to',
] as const;

function Detail({ id, onClose }: { id: string; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ['admin', 'query', id],
    queryFn: ({ signal }) => api.queryDetail(id, signal),
  });
  const data = detail.data;
  return (
    <Dialog.Root open onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="drawer admin-drawer" aria-describedby={undefined}>
          <div className="drawer-head">
            <Dialog.Title className="drawer-title">Запрос</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Закрыть">
              <X size={18} />
            </Dialog.Close>
          </div>
          {detail.isPending && <div className="skeleton-block" />}
          {detail.isError && (
            <p role="alert" className="error-box">
              Не удалось загрузить запрос: {detail.error.message}
            </p>
          )}
          {data && (
            <div className="admin-detail">
              <p className="detail-query">{data.query}</p>
              <dl className="detail-meta">
                <dt>Время</dt>
                <dd>{dateTime(data.created_at)}</dd>
                <dt>Язык · режим</dt>
                <dd>
                  {data.lang} · {data.mode} · top {data.top_k}
                </dd>
                <dt>Фильтры</dt>
                <dd>
                  {data.filters.in_force_only ? 'только действующие' : 'все редакции'}
                  {data.filters.doc_ids?.length
                    ? ` · документы: ${data.filters.doc_ids.join(', ')}`
                    : ''}
                  {data.filters.doc_types?.length
                    ? ` · типы: ${data.filters.doc_types.join(', ')}`
                    : ''}
                </dd>
                <dt>Пайплайн</dt>
                <dd>{data.pipeline_version ?? '—'}</dd>
                {!!data.degraded?.length && (
                  <>
                    <dt>Деградация</dt>
                    <dd>{data.degraded.map((item) => DEGRADED_LABELS[item] ?? item).join('; ')}</dd>
                  </>
                )}
              </dl>

              <h3>Время поиска</h3>
              <TimingBar timing={data.timing_ms} />

              <h3>Результаты ({data.results.length})</h3>
              {data.results.length === 0 ? (
                <p className="admin-empty">Ничего не найдено</p>
              ) : (
                <ol className="detail-results">
                  {data.results.map((result) => (
                    <li key={result.rank}>
                      <Link
                        to={`/?article=${encodeURIComponent(result.article_id)}`}
                        target="_blank"
                      >
                        {result.doc_short_title ? `${result.doc_short_title} · ` : ''}
                        {result.title || result.article_id}
                      </Link>
                      <span className="detail-score">{result.score.toFixed(3)}</span>
                    </li>
                  ))}
                </ol>
              )}

              <h3>Ответ ИИ</h3>
              {data.answer ? (
                <>
                  <p className="detail-answer">{data.answer.text}</p>
                  <p className="admin-note">
                    Ссылки:{' '}
                    {data.answer.citations.length
                      ? data.answer.citations.map((n) => `[${n}]`).join(' ')
                      : 'нет'}{' '}
                    · {data.answer.grounded ? 'опирается на источники' : 'без опоры на источники'} ·
                    первый токен {milliseconds(data.answer.timing_ms.ttft)} · всего{' '}
                    {milliseconds(data.answer.timing_ms.total)}
                  </p>
                </>
              ) : (
                <p className="admin-empty">Ответ не запрашивался</p>
              )}

              <h3>Оценки ({data.feedback_items.length})</h3>
              {data.feedback_items.length === 0 ? (
                <p className="admin-empty">Оценок нет</p>
              ) : (
                <ul className="detail-feedback">
                  {data.feedback_items.map((item, index) => (
                    <li key={index}>
                      {item.rating > 0 ? '👍' : '👎'}{' '}
                      {item.target === 'answer' ? 'ответ' : `результат ${item.article_id}`}
                      {item.comment ? ` — «${item.comment}»` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function Queries() {
  const [params, setParams] = useSearchParams();
  const [exportError, setExportError] = useState('');
  const filters: api.QueryFilters = compact(
    Object.fromEntries(FILTER_KEYS.map((key) => [key, params.get(key) ?? undefined])),
  );
  const page = Math.max(1, Number(params.get('page')) || 1);
  const openId = params.get('open');
  const list = useQuery({
    queryKey: ['admin', 'queries', filters, page],
    queryFn: ({ signal }) => api.queries(filters, page, PAGE_SIZE, signal),
    placeholderData: keepPreviousData,
  });

  /** Filters, the page and the open row all live in the URL: a link reproduces the view. */
  function update(changes: Record<string, string | undefined>, keepPage = false) {
    const next = compact({
      ...Object.fromEntries(params.entries()),
      ...changes,
      ...(keepPage ? {} : { page: undefined }),
    });
    setParams(next);
  }
  const toggle = (key: 'zero_results' | 'degraded', on: boolean) =>
    update({ [key]: on ? 'true' : undefined });
  const pages = list.data ? Math.max(1, Math.ceil(list.data.total / PAGE_SIZE)) : 1;

  return (
    <>
      <div className="admin-toolbar">
        <h1>Журнал запросов</h1>
        <Button
          className="secondary"
          onClick={() => {
            setExportError('');
            api.downloadCsv(filters).catch((error: Error) => setExportError(error.message));
          }}
        >
          <Download size={15} /> Экспорт CSV
        </Button>
      </div>
      {exportError && (
        <p role="alert" className="error-box">
          Экспорт не удался: {exportError}
        </p>
      )}
      <form className="admin-filters" onSubmit={(event) => event.preventDefault()}>
        <label>
          Текст запроса
          <input
            type="search"
            defaultValue={filters.q ?? ''}
            key={filters.q ?? ''}
            placeholder="часть запроса"
            onKeyDown={(event) => {
              if (event.key === 'Enter')
                update({ q: event.currentTarget.value.trim() || undefined });
            }}
            onBlur={(event) => {
              const value = event.currentTarget.value.trim();
              if (value !== (filters.q ?? '')) update({ q: value || undefined });
            }}
          />
        </label>
        <label>
          Язык
          <select
            value={filters.lang ?? ''}
            onChange={(event) => update({ lang: event.target.value || undefined })}
          >
            <option value="">любой</option>
            <option value="ru">русский</option>
            <option value="kk">қазақша</option>
          </select>
        </label>
        <label>
          Режим
          <select
            value={filters.mode ?? ''}
            onChange={(event) => update({ mode: event.target.value || undefined })}
          >
            <option value="">любой</option>
            <option value="hybrid">гибридный</option>
            <option value="semantic">семантический</option>
            <option value="keyword">ключевые слова</option>
          </select>
        </label>
        <label>
          С
          <input
            type="date"
            value={filters.date_from ?? ''}
            onChange={(event) => update({ date_from: event.target.value || undefined })}
          />
        </label>
        <label>
          По
          <input
            type="date"
            value={filters.date_to ?? ''}
            onChange={(event) => update({ date_to: event.target.value || undefined })}
          />
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.zero_results === 'true'}
            onChange={(event) => toggle('zero_results', event.target.checked)}
          />
          без результатов
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.feedback === 'negative'}
            onChange={(event) =>
              update({ feedback: event.target.checked ? 'negative' : undefined })
            }
          />
          с оценкой 👎
        </label>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={filters.degraded === 'true'}
            onChange={(event) => toggle('degraded', event.target.checked)}
          />
          с деградацией
        </label>
        {Object.keys(filters).length > 0 && (
          <button type="button" className="text-button" onClick={() => setParams({})}>
            Сбросить фильтры
          </button>
        )}
      </form>

      {list.isError && (
        <div role="alert" className="error-box">
          <p>Не удалось загрузить журнал: {list.error.message}</p>
        </div>
      )}
      {list.isPending && <div className="skeleton-block" />}
      {list.data && (
        <>
          <p className="admin-note" aria-live="polite">
            Найдено: {list.data.total}
          </p>
          {list.data.items.length === 0 ? (
            <p className="admin-empty">Запросов с такими условиями нет</p>
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Время</th>
                    <th>Запрос</th>
                    <th>Язык</th>
                    <th>Режим</th>
                    <th className="numeric">Найдено</th>
                    <th className="numeric">Поиск</th>
                    <th>Ответ</th>
                    <th>Оценки</th>
                    <th>Деградация</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((item) => (
                    <tr
                      key={item.query_id}
                      className={item.result_count === 0 ? 'row-zero' : undefined}
                    >
                      <td className="nowrap">{dateTime(item.created_at)}</td>
                      <td>
                        <button
                          className="link-button"
                          onClick={() => update({ open: item.query_id }, true)}
                        >
                          {item.query}
                        </button>
                      </td>
                      <td>{item.lang}</td>
                      <td>{item.mode}</td>
                      <td className="numeric">{item.result_count}</td>
                      <td className="numeric nowrap">{milliseconds(item.search_ms)}</td>
                      <td>{item.has_answer ? '✓' : ''}</td>
                      <td className="nowrap">
                        {item.feedback.positive > 0 && `👍 ${item.feedback.positive} `}
                        {item.feedback.negative > 0 && `👎 ${item.feedback.negative}`}
                      </td>
                      <td>{item.degraded?.join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="admin-pager">
            <Button
              className="secondary"
              disabled={page <= 1}
              onClick={() => update({ page: String(page - 1) }, true)}
            >
              ← Назад
            </Button>
            <span>
              Страница {page} из {pages}
            </span>
            <Button
              className="secondary"
              disabled={page >= pages}
              onClick={() => update({ page: String(page + 1) }, true)}
            >
              Вперёд →
            </Button>
          </div>
        </>
      )}
      {openId && <Detail id={openId} onClose={() => update({ open: undefined }, true)} />}
    </>
  );
}
