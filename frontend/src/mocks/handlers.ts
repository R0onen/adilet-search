import { http, HttpResponse, delay } from 'msw';
import fixtures from './articles';
import type {
  ArticleDetail,
  Schemas,
  SearchRequest,
  SearchResponse,
  SearchResult,
} from '../api/types';

export const articles: ArticleDetail[] = fixtures;
export function mockSearch(request: SearchRequest): SearchResponse {
  const query = request.query.trim();
  const lang =
    request.lang === 'auto' || !request.lang
      ? /[әғқңөұүһі]/i.test(query)
        ? 'kk'
        : 'ru'
      : request.lang;
  const words = query
    .toLocaleLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((word) => word.length > 2);
  const topic = /зарплат|заработ|жалақы|salary/i.test(query)
    ? ['a114', 'a113']
    : /увол|сокращ|жұмыстан|қысқар|dismiss/i.test(query)
      ? ['a52']
      : /эколог|выброс|ласта|emission/i.test(query)
        ? ['a10']
        : [];
  const filters = request.filters;
  const candidates = articles
    .filter(
      (item) =>
        item.lang === lang &&
        (!(filters?.in_force_only ?? true) ||
          (item.doc.status === 'in_force' && item.article.unit_status === 'in_force')) &&
        (!filters?.doc_ids?.length || filters.doc_ids.includes(item.doc.doc_id)) &&
        (!filters?.doc_types?.length || filters.doc_types.includes(item.doc.doc_type)) &&
        (!filters?.date_from ||
          (!!item.doc.adopted_date && item.doc.adopted_date >= filters.date_from)) &&
        (!filters?.date_to ||
          (!!item.doc.adopted_date && item.doc.adopted_date <= filters.date_to)),
    )
    .map((item) => {
      const text = `${item.article.title} ${item.text}`.toLocaleLowerCase();
      const matches = words.filter((word) => text.includes(word)).length;
      const topicRank = topic.indexOf(item.article.article_id.split(':')[2]);
      const score = request.mode !== 'keyword' && topicRank >= 0 ? 10 - topicRank : matches;
      return { item, score };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score);
  const results: SearchResult[] = candidates
    .slice(0, request.top_k || 10)
    .map(({ item, score }, index) => ({
      rank: index + 1,
      article: item.article,
      doc: item.doc,
      chunk_id: `${item.article.article_id}:c0`,
      lang,
      score: Math.min(score / 10, 1),
      score_type: request.mode === 'keyword' ? 'fts' : 'rerank',
      snippet: item.text.slice(0, 300),
      highlights: [],
    }));
  return {
    query_id: crypto.randomUUID(),
    query,
    lang,
    mode: request.mode || 'hybrid',
    results,
    total_candidates: candidates.length,
    degraded: [],
    timing_ms: {},
    pipeline_version: 'synthetic-demo',
  };
}
const error = (message: string, status = 501) =>
  HttpResponse.json(
    {
      error: {
        code: status === 404 ? 'not_found' : 'not_implemented',
        message,
        details: null,
        request_id: crypto.randomUUID(),
      },
    },
    { status },
  );
export const handlers = [
  http.post('/api/v1/search', async ({ request }) => {
    const body = (await request.json()) as SearchRequest;
    await delay(350);
    if (!body.query?.trim() || body.query.trim().length > 500)
      return error('Query must be 1–500 characters', 422);
    if (body.query === '/error') return error('Simulated service failure', 503);
    return HttpResponse.json(mockSearch(body));
  }),
  http.get('/api/v1/articles/:id', async ({ params }) => {
    await delay(160);
    const result = articles.find(
      (item) => item.article.article_id === decodeURIComponent(String(params.id)),
    );
    return result ? HttpResponse.json(result) : error('Article not found', 404);
  }),
  http.get('/api/v1/documents', ({ request }) => {
    const url = new URL(request.url);
    const lang = url.searchParams.get('lang') || 'ru';
    const docs = [
      ...new Map(
        articles.filter((item) => item.lang === lang).map((item) => [item.doc.doc_id, item.doc]),
      ).values(),
    ];
    return HttpResponse.json({
      items: docs.map((doc) => ({
        ...doc,
        article_count: articles.filter(
          (item) => item.doc.doc_id === doc.doc_id && item.lang === lang,
        ).length,
      })),
      page: 1,
      page_size: 20,
      total: docs.length,
    });
  }),
  http.get('/api/v1/documents/:id', ({ params, request }) => {
    const lang = new URL(request.url).searchParams.get('lang') || 'ru';
    const items = articles.filter((item) => item.doc.doc_id === params.id && item.lang === lang);
    return items.length
      ? HttpResponse.json({ ...items[0].doc, toc: items.map((item) => item.article) })
      : error('Document not found', 404);
  }),
  http.post('/api/v1/answer', async ({ request }) => {
    const body = (await request.json()) as SearchRequest;
    if (body.query.includes('/answer-error'))
      return error('Simulated answer endpoint not implemented');
    const result = mockSearch(body);
    const sources = result.results
      .slice(0, 3)
      .map((item, index) => ({
        ref: index + 1,
        article: item.article,
        doc: item.doc,
        snippet: item.snippet,
      }));
    const text = sources.length
      ? (result.lang === 'kk'
          ? 'Бұл — алдын ала дайындалған синтетикалық жауап, нақты AI нәтижесі емес. Сынақ мәтініндегі сәйкес үзінділер:\n\n'
          : 'Это заранее подготовленный синтетический ответ, а не результат работы AI. Подходящие фрагменты тестовых документов:\n\n') +
        sources.map((source) => `${source.snippet.split('\n\n')[0]} [${source.ref}]`).join('\n\n')
      : result.lang === 'kk'
        ? 'Сынақ деректерінен сәйкес мәтін табылмады.'
        : 'В тестовых данных подходящих текстов не найдено.';
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        const emit = (event: string, data: unknown) =>
          controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        try {
          emit('sources', {
            query_id: result.query_id,
            lang: result.lang,
            sources,
            degraded: [],
          } satisfies Schemas['SourcesEvent']);
          if (body.query.includes('/stream-error')) {
            emit('error', {
              code: 'generation_unavailable',
              message: 'Simulated generator outage',
            });
            controller.close();
            return;
          }
          for (const token of text.match(/\S+\s*/g) || []) {
            await delay(22);
            if (request.signal.aborted) {
              controller.close();
              return;
            }
            emit('token', { text: token });
          }
          emit('done', {
            answer_id: crypto.randomUUID(),
            text,
            citations: sources.map((source) => source.ref),
            invalid_citations_removed: 0,
            grounded: !!sources.length,
            finish_reason: 'stop',
            timing_ms: {},
            pipeline_version: 'synthetic-demo',
          } satisfies Schemas['DoneEvent']);
          controller.close();
        } catch {
          /* The reader can cancel the mock stream. */
        }
      },
    });
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } });
  }),
  http.post('/api/v1/feedback', () => new HttpResponse(null, { status: 204 })),
  http.get('/api/v1/health', () =>
    HttpResponse.json({
      status: 'ok',
      components: { database: 'ok', qdrant: 'ok', ml_service: 'ok', llm: 'ok' },
      pipeline_version: 'synthetic-demo',
      app_version: '0.1.0-demo',
    } satisfies Schemas['HealthResponse']),
  ),
  http.get('/api/v1/version', () =>
    HttpResponse.json({
      app_version: '0.1.0-demo',
      git_sha: 'demo',
      pipeline_version: 'synthetic-demo',
      index_collection: null,
    } satisfies Schemas['VersionResponse']),
  ),
  http.all('/api/v1/admin/*', () => error('Admin is outside the presentation MVP')),
];
