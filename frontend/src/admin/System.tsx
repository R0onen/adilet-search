import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import * as api from '../api/admin';
import { Button } from '../components/ui/button';
import { dateTime } from './format';

const COMPONENT_LABELS: Record<string, string> = {
  database: 'База данных (PostgreSQL)',
  qdrant: 'Векторный индекс (Qdrant)',
  ml_service: 'ML-сервис',
  llm: 'Генератор ответов (LLM)',
};
const STATUS_LABELS: Record<string, string> = {
  ok: 'работает',
  degraded: 'частично',
  down: 'недоступен',
  unavailable: 'не настроен',
};
const JOB_LABELS: Record<string, string> = {
  queued: 'в очереди',
  running: 'выполняется',
  succeeded: 'завершена',
  failed: 'ошибка',
};

function uptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours} ч ${minutes} мин` : `${minutes} мин`;
}

function JobProgress({ jobId, onFinished }: { jobId: string; onFinished: () => void }) {
  const job = useQuery({
    queryKey: ['admin', 'job', jobId],
    queryFn: async ({ signal }) => {
      const data = await api.job(jobId, signal);
      if (data.status === 'succeeded' || data.status === 'failed') onFinished();
      return data;
    },
    // Poll every 2 s while the job is active, then stop.
    refetchInterval: (query) =>
      query.state.data && ['succeeded', 'failed'].includes(query.state.data.status) ? false : 2000,
    staleTime: 0,
  });
  const data = job.data;
  if (!data) return <div className="skeleton-block" />;
  return (
    <div className={`job-box job-${data.status}`} role="status">
      <strong>Переиндексация: {JOB_LABELS[data.status] ?? data.status}</strong>
      <progress max={1} value={data.progress} aria-label="Прогресс переиндексации" />
      <span>
        {Math.round(data.progress * 100)}%{data.message ? ` · ${data.message}` : ''}
      </span>
    </div>
  );
}

function ReindexDialog({ onStarted }: { onStarted: (jobId: string) => void }) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState<'processed' | 'sample'>('processed');
  const [precomputed, setPrecomputed] = useState(true);
  const start = useMutation({
    mutationFn: () => api.reindex(source, precomputed),
    onSuccess: (ref) => {
      setOpen(false);
      onStarted(ref.job_id);
    },
  });
  const error = start.error instanceof api.AdminError ? start.error : null;
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        start.reset();
      }}
    >
      <Dialog.Trigger asChild>
        <Button className="secondary">
          <RefreshCw size={15} /> Переиндексировать
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content className="admin-dialog">
          <Dialog.Title>Переиндексация</Dialog.Title>
          <Dialog.Description>
            Новый индекс строится рядом с текущим. Поиск продолжает работать на старом индексе и
            переключается на новый только после успешного завершения. При ошибке ничего не меняется.
            Полный корпус на CPU индексируется около 45 минут.
          </Dialog.Description>
          <label>
            Корпус
            <select
              value={source}
              onChange={(event) => setSource(event.target.value as 'processed' | 'sample')}
            >
              <option value="processed">полный (processed)</option>
              <option value="sample">образец (sample)</option>
            </select>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={precomputed}
              onChange={(event) => setPrecomputed(event.target.checked)}
            />
            использовать готовые эмбеддинги, если они есть
          </label>
          {start.isError && (
            <p role="alert" className="admin-form-error">
              {error?.status === 409
                ? 'Переиндексация уже выполняется'
                : error?.status === 422
                  ? `Корпус не найден на сервере: ${error.message}`
                  : `Не удалось запустить: ${start.error.message}`}
            </p>
          )}
          <div className="dialog-actions">
            <Dialog.Close asChild>
              <Button className="secondary">Отмена</Button>
            </Dialog.Close>
            <Button onClick={() => start.mutate()} disabled={start.isPending}>
              {start.isPending ? 'Запускаем…' : 'Запустить'}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function System() {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const system = useQuery({
    queryKey: ['admin', 'system'],
    queryFn: ({ signal }) => api.system(signal),
    refetchInterval: 30_000,
    staleTime: 0,
  });
  const data = system.data;
  // A job that was already running when the page opened is followed too.
  const activeJob =
    jobId ??
    (data?.index.last_job && ['queued', 'running'].includes(data.index.last_job.status)
      ? data.index.last_job.job_id
      : null);
  return (
    <>
      <div className="admin-toolbar">
        <h1>Система</h1>
        {system.dataUpdatedAt > 0 && (
          <span className="admin-note">
            Проверено: {new Date(system.dataUpdatedAt).toLocaleTimeString('ru-RU')} · обновляется
            каждые 30 с
          </span>
        )}
      </div>
      {system.isError && (
        <div role="alert" className="error-box">
          <p>Не удалось получить состояние системы: {system.error.message}</p>
        </div>
      )}
      {system.isPending && <div className="skeleton-block" />}
      {data && (
        <div className="admin-grid">
          <div className="admin-card">
            <h2>Компоненты</h2>
            <ul className="component-list">
              {Object.entries(data.components).map(([name, status]) => (
                <li key={name}>
                  <span className={`status-dot status-${status}`} aria-hidden="true" />
                  <span>{COMPONENT_LABELS[name] ?? name}</span>
                  <strong>{STATUS_LABELS[status] ?? status}</strong>
                </li>
              ))}
            </ul>
            <p className="admin-note">
              Версия {data.app_version} ({data.git_sha}) · работает {uptime(data.uptime_s)}
            </p>
            <p className="admin-note">
              <a className="text-button" href="/grafana/" target="_blank" rel="noreferrer">
                Открыть Grafana →
              </a>
            </p>
          </div>

          <div className="admin-card">
            <h2>Модели</h2>
            <dl className="detail-meta">
              <dt>Версия пайплайна</dt>
              <dd>{data.pipeline.pipeline_version ?? '—'}</dd>
              <dt>Эмбеддер</dt>
              <dd>{data.pipeline.embedder ?? '—'}</dd>
              <dt>Реранкер</dt>
              <dd>{data.pipeline.reranker ?? '—'}</dd>
              <dt>Генератор</dt>
              <dd>{data.pipeline.generator ?? '—'}</dd>
              <dt>index_compat_id</dt>
              <dd>{data.pipeline.index_compat_id ?? '—'}</dd>
            </dl>
          </div>

          <div className="admin-card admin-card-wide">
            <h2>Индекс</h2>
            {!data.index.compatible && (
              <p role="alert" className="error-box">
                Требуется переиндексация: индекс построен другими моделями или ещё не создан. Поиск
                работает в упрощённом режиме (полнотекстовый).
              </p>
            )}
            <dl className="detail-meta">
              <dt>Алиас → коллекция</dt>
              <dd>
                {data.index.alias} → {data.index.collection ?? 'нет'}
              </dd>
              <dt>Точек (фрагментов)</dt>
              <dd>{data.index.points ?? '—'}</dd>
              <dt>Документов · статей</dt>
              <dd>
                {data.index.documents ?? '—'} · {data.index.articles ?? '—'}
              </dd>
              <dt>index_compat_id индекса</dt>
              <dd>{data.index.index_compat_id ?? '—'}</dd>
              <dt>Последняя задача</dt>
              <dd>
                {data.index.last_job
                  ? `${JOB_LABELS[data.index.last_job.status] ?? data.index.last_job.status}, ${dateTime(data.index.last_job.created_at)}${data.index.last_job.status === 'failed' && data.index.last_job.message ? ` — ${data.index.last_job.message}` : ''}`
                  : 'нет'}
              </dd>
            </dl>
            {activeJob ? (
              <JobProgress
                jobId={activeJob}
                onFinished={() =>
                  void queryClient.invalidateQueries({ queryKey: ['admin', 'system'] })
                }
              />
            ) : (
              <ReindexDialog onStarted={setJobId} />
            )}
            {jobId && !['queued', 'running'].includes(data.index.last_job?.status ?? '') && (
              <p className="admin-note">
                <button className="text-button" onClick={() => setJobId(null)}>
                  Скрыть результат задачи
                </button>
              </p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
