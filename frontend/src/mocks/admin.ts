/** Mock admin API for demo mode and tests. Login: admin / demo. All numbers are invented. */
import { http, HttpResponse } from 'msw';
import type { Schemas } from '../api/types';

export const MOCK_TOKEN = 'mock-admin-token';
export const ZERO_QUERY = 'налог на роскошь';

function error(status: number, message: string, headers?: Record<string, string>) {
  return HttpResponse.json(
    { error: { code: 'error', message, details: null, request_id: 'mock' } },
    { status, headers },
  );
}
function authorised(request: Request): boolean {
  return request.headers.get('Authorization') === `Bearer ${MOCK_TOKEN}`;
}

const ITEMS: Schemas['QueryLogItem'][] = [
  ['Мне не платят зарплату', 'ru', 'hybrid', 10, 412, true, 1, 0, []],
  [ZERO_QUERY, 'ru', 'hybrid', 0, 180, false, 0, 0, []],
  ['Жалақымды төлемейді', 'kk', 'hybrid', 8, 530, false, 0, 1, ['rerank']],
  ['основания расторжения трудового договора', 'ru', 'keyword', 6, 95, false, 0, 0, []],
  [ZERO_QUERY, 'ru', 'semantic', 0, 240, false, 0, 0, ['semantic']],
].map(([query, lang, mode, count, ms, answer, up, down, degraded], index) => ({
  query_id: `00000000-0000-4000-8000-00000000000${index + 1}`,
  created_at: `2026-11-0${5 - index}T10:1${index}:00Z`,
  query: query as string,
  lang: lang as 'ru' | 'kk',
  mode: mode as 'hybrid' | 'semantic' | 'keyword',
  result_count: count as number,
  top_article_id: count ? 'T0000000001:ru:a114' : null,
  search_ms: ms as number,
  has_answer: answer as boolean,
  feedback: { positive: up as number, negative: down as number },
  degraded: degraded as Schemas['QueryLogItem']['degraded'],
}));

const STATS: Schemas['StatsResponse'] = {
  date_from: '2026-11-01',
  date_to: '2026-11-07',
  totals: {
    queries: 1240,
    unique_sessions: 310,
    answers: 402,
    feedback_positive: 88,
    feedback_negative: 17,
    zero_result_queries: 31,
  },
  rates: { zero_result_rate: 0.025, satisfaction_rate: 0.838, degraded_rate: 0.004 },
  latency_ms: { search_p50: 380, search_p95: 910, answer_ttft_p50: 2100, answer_ttft_p95: 3900 },
  by_day: [150, 170, 0, 210, 190, 260, 260].map((queries, index) => ({
    date: `2026-11-0${index + 1}`,
    queries,
    search_p95_ms: queries ? 800 + index * 40 : null,
    zero_result_rate: queries ? 0.02 : null,
  })),
  by_lang: [
    { lang: 'ru', queries: 1010 },
    { lang: 'kk', queries: 230 },
  ],
  by_mode: [
    { mode: 'hybrid', queries: 1100 },
    { mode: 'keyword', queries: 140 },
  ],
  top_queries: [
    { query: 'мне не платят зарплату', count: 12 },
    { query: 'основания расторжения трудового договора', count: 9 },
  ],
  top_zero_result_queries: [{ query: ZERO_QUERY, count: 4 }],
};

let jobPolls = 0;
const job = (progress: number, status: Schemas['Job']['status']): Schemas['Job'] => ({
  job_id: '0c9d8e7f-6a5b-4c3d-8e2f-1a0b9c8d7e6f',
  kind: 'reindex',
  status,
  progress,
  message: status === 'succeeded' ? 'done' : `embedded ${Math.round(progress * 800)}/800 chunks`,
  created_at: '2026-11-05T09:00:00Z',
  started_at: '2026-11-05T09:00:01Z',
  finished_at: status === 'succeeded' ? '2026-11-05T09:03:00Z' : null,
});

export const adminHandlers = [
  http.post('/api/v1/admin/login', async ({ request }) => {
    const body = (await request.json()) as Schemas['LoginRequest'];
    if (body.username === 'admin' && body.password === 'demo')
      return HttpResponse.json({
        access_token: MOCK_TOKEN,
        token_type: 'bearer',
        expires_in: 28800,
      } satisfies Schemas['TokenResponse']);
    if (body.username === 'limited')
      return error(429, 'Too many requests', { 'Retry-After': '42' });
    return error(401, 'Wrong username or password');
  }),
  http.all('/api/v1/admin/*', ({ request }) => {
    if (!authorised(request)) return error(401, 'Authentication required');
    return undefined; // fall through to the handlers below
  }),
  http.get('/api/v1/admin/stats', () => HttpResponse.json(STATS)),
  http.get(
    '/api/v1/admin/queries/export',
    () =>
      new HttpResponse('﻿query_id,created_at,query\r\n', {
        headers: { 'Content-Type': 'text/csv; charset=utf-8' },
      }),
  ),
  http.get('/api/v1/admin/queries/:id', ({ params }) => {
    const item = ITEMS.find((candidate) => candidate.query_id === params.id);
    if (!item) return error(404, 'Query not found');
    return HttpResponse.json({
      ...item,
      filters: { doc_types: [], doc_ids: [], in_force_only: true, date_from: null, date_to: null },
      top_k: 10,
      results: item.result_count
        ? [
            {
              rank: 1,
              article_id: 'T0000000001:ru:a114',
              title: 'Ответственность работодателя за задержку заработной платы',
              doc_short_title: 'Тестовый ТК',
              score: 0.91,
            },
          ]
        : [],
      timing_ms: { embed: 41, retrieve: 18, fuse: 1, rerank: 312, total: item.search_ms ?? 0 },
      answer: item.has_answer
        ? {
            answer_id: 'b7e4d1c2-8f3a-4e6b-9d05-1a2c3e4f5a6b',
            text: 'Работодатель несёт ответственность за задержку заработной платы [1].',
            citations: [1],
            grounded: true,
            timing_ms: { search: 402, ttft: 1900, total: 6100 },
          }
        : null,
      feedback_items: item.feedback.positive
        ? [
            {
              target: 'answer',
              article_id: null,
              rating: 1,
              comment: null,
              created_at: '2026-11-05T10:14:02Z',
            },
          ]
        : [],
      pipeline_version: 'synthetic-demo',
      session_hash: 'ab12',
    } satisfies Schemas['QueryLogDetail']);
  }),
  http.get('/api/v1/admin/queries', ({ request }) => {
    const params = new URL(request.url).searchParams;
    const text = (params.get('q') || '').toLocaleLowerCase();
    const filtered = ITEMS.filter(
      (item) =>
        (!text || item.query.toLocaleLowerCase().includes(text)) &&
        (!params.get('lang') || item.lang === params.get('lang')) &&
        (!params.get('mode') || item.mode === params.get('mode')) &&
        (params.get('zero_results') !== 'true' || item.result_count === 0) &&
        (params.get('degraded') !== 'true' || !!item.degraded?.length) &&
        (params.get('feedback') !== 'negative' || item.feedback.negative > 0),
    );
    const page = Number(params.get('page')) || 1;
    const pageSize = Number(params.get('page_size')) || 20;
    return HttpResponse.json({
      items: filtered.slice((page - 1) * pageSize, page * pageSize),
      page,
      page_size: pageSize,
      total: filtered.length,
    } satisfies Schemas['QueryLogPage']);
  }),
  http.get('/api/v1/admin/system', () =>
    HttpResponse.json({
      components: { database: 'ok', qdrant: 'ok', ml_service: 'ok', llm: 'unavailable' },
      app_version: '0.1.0-demo',
      git_sha: 'demo',
      uptime_s: 5400,
      pipeline: {
        pipeline_version: 'synthetic-demo',
        embedder: 'demo-embedder',
        reranker: 'demo-reranker',
        generator: null,
        index_compat_id: 'demo',
      },
      index: {
        alias: 'legal_chunks',
        collection: 'legal_chunks__demo',
        points: 800,
        documents: 2,
        articles: 454,
        index_compat_id: 'demo',
        compatible: true,
        last_job: null,
      },
    } satisfies Schemas['SystemResponse']),
  ),
  http.post('/api/v1/admin/reindex', async ({ request }) => {
    const body = (await request.json()) as Schemas['ReindexRequest'];
    if (body.source === 'sample') return error(409, 'An index job is already queued or running');
    jobPolls = 0;
    return HttpResponse.json({ job_id: job(0, 'queued').job_id }, { status: 202 });
  }),
  http.get('/api/v1/admin/jobs/:id', () => {
    jobPolls += 1;
    return HttpResponse.json(jobPolls >= 3 ? job(1, 'succeeded') : job(jobPolls / 3, 'running'));
  }),
];
