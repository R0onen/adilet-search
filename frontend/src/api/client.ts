import createClient from 'openapi-fetch';
import type { paths } from './schema';
import type { SearchRequest } from './types';

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
    throw new ApiError(response.status, error?.error.message || response.statusText);
  return data;
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
