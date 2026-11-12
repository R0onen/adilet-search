import type { Schemas } from './types';

export type Stats = Schemas['StatsResponse'];
export type QueryLogItem = Schemas['QueryLogItem'];
export type QueryLogPage = Schemas['QueryLogPage'];
export type QueryLogDetail = Schemas['QueryLogDetail'];
export type SystemInfo = Schemas['SystemResponse'];
export type Job = Schemas['Job'];

/** Filters of the query log. They live in the URL, so every value is a string. */
export type QueryFilters = Partial<
  Record<
    'q' | 'lang' | 'mode' | 'zero_results' | 'feedback' | 'degraded' | 'date_from' | 'date_to',
    string
  >
>;

export class AdminError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: number,
  ) {
    super(message);
    this.name = 'AdminError';
  }
}

const TOKEN_KEY = 'adilet_admin_token';
let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

/** The JWT is kept in memory and mirrored to sessionStorage, so it survives a reload only. */
export function loadToken(): string | null {
  if (token) return token;
  try {
    token = sessionStorage.getItem(TOKEN_KEY);
  } catch {
    token = null;
  }
  return token;
}
export function storeToken(value: string | null) {
  token = value;
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* private mode: the token stays in memory only */
  }
}
/** Called once by the auth provider: any 401 from an admin call logs the user out. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

async function failure(response: Response): Promise<AdminError> {
  let message = response.statusText;
  try {
    const body = (await response.json()) as Schemas['ErrorResponse'];
    message = body.error.message || message;
  } catch {
    /* not JSON: keep the status text */
  }
  const retryAfter = Number(response.headers.get('Retry-After')) || undefined;
  return new AdminError(response.status, message, retryAfter);
}

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params))
    if (value !== undefined && value !== '') search.set(key, String(value));
  const text = search.toString();
  return text ? `?${text}` : '';
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const current = loadToken();
  if (current) headers.set('Authorization', `Bearer ${current}`);
  if (init.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api/v1/admin${path}`, { ...init, headers });
  if (response.status === 401 && path !== '/login') {
    storeToken(null);
    onUnauthorized?.();
  }
  if (!response.ok) throw await failure(response);
  return response;
}
async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return (await (await request(path, init)).json()) as T;
}

export async function login(username: string, password: string): Promise<void> {
  const body = await json<Schemas['TokenResponse']>('/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  storeToken(body.access_token);
}
export const stats = (dateFrom: string, dateTo: string, signal?: AbortSignal) =>
  json<Stats>(`/stats${query({ date_from: dateFrom, date_to: dateTo })}`, { signal });
export const queries = (
  filters: QueryFilters,
  page: number,
  pageSize: number,
  signal?: AbortSignal,
) => json<QueryLogPage>(`/queries${query({ ...filters, page, page_size: pageSize })}`, { signal });
export const queryDetail = (id: string, signal?: AbortSignal) =>
  json<QueryLogDetail>(`/queries/${id}`, { signal });
export const system = (signal?: AbortSignal) => json<SystemInfo>('/system', { signal });
export const job = (id: string, signal?: AbortSignal) => json<Job>(`/jobs/${id}`, { signal });
export const reindex = (source: 'processed' | 'sample', usePrecomputed: boolean) =>
  json<Schemas['JobRef']>('/reindex', {
    method: 'POST',
    body: JSON.stringify({ source, use_precomputed_embeddings: usePrecomputed }),
  });

/** The export needs the Authorization header, so it cannot be a plain link. */
export async function downloadCsv(filters: QueryFilters): Promise<void> {
  const response = await request(`/queries/export${query(filters)}`);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = 'adilet-queries.csv';
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
