import createClient from 'openapi-fetch';
import type { paths } from './schema';
import type { Schemas, SearchRequest } from './types';

export const apiMode = import.meta.env.VITE_API_MODE === 'live' ? 'live' : 'mock';
let sessionId: string | undefined;
export function sessionHeaders(): Record<string, string> {
  if (!sessionId) {
    try {
      sessionId = localStorage.getItem('adilet_session_id') || crypto.randomUUID();
      localStorage.setItem('adilet_session_id', sessionId);
    } catch {
      sessionId = crypto.randomUUID();
    }
  }
  return { 'X-Session-Id': sessionId };
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Seconds to wait, from the Retry-After header of a 429. */
    public retryAfter?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
export const client = createClient<paths>({ baseUrl: '' });
client.use({
  onRequest({ request }) {
    Object.entries(sessionHeaders()).forEach(([key, value]) => request.headers.set(key, value));
    return request;
  },
});
export async function search(request: SearchRequest, signal?: AbortSignal) {
  const { data, error, response } = await client.POST('/api/v1/search', { body: request, signal });
  if (error || !data)
    throw new ApiError(
      response.status,
      error?.error.message || response.statusText,
      Number(response.headers.get('Retry-After')) || undefined,
    );
  return data;
}
export async function feedback(body: Schemas['FeedbackRequest']) {
  const { error, response } = await client.POST('/api/v1/feedback', { body });
  if (error) throw new ApiError(response.status, error.error.message || response.statusText);
}
export async function article(articleId: string, signal?: AbortSignal) {
  const { data, error, response } = await client.GET('/api/v1/articles/{article_id}', {
    params: { path: { article_id: articleId } },
    signal,
  });
  if (error || !data)
    throw new ApiError(response.status, error?.error.message || response.statusText);
  return data;
}
export async function documents(lang: 'ru' | 'kk', signal?: AbortSignal) {
  const { data, error, response } = await client.GET('/api/v1/documents', {
    params: { query: { lang, page_size: 100 } },
    signal,
  });
  if (error || !data)
    throw new ApiError(response.status, error?.error.message || response.statusText);
  return data;
}
