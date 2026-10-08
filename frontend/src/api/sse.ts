import { ApiError, sessionHeaders } from './client';
import type { DoneEvent, ErrorEvent, Schemas, SearchRequest, SourcesEvent } from './types';

export type StreamEvent = { event: string; data: string };
export async function* parseSSE(stream: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let event = '';
  let data: string[] = [];
  const line = (value: string): StreamEvent | undefined => {
    if (value === '') {
      const result = data.length ? { event: event || 'message', data: data.join('\n') } : undefined;
      event = '';
      data = [];
      return result;
    }
    if (value.startsWith(':')) return;
    const colon = value.indexOf(':');
    const key = colon < 0 ? value : value.slice(0, colon);
    const field = colon < 0 ? '' : value.slice(colon + 1).replace(/^ /, '');
    if (key === 'event') event = field;
    if (key === 'data') data.push(field);
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let match: RegExpExecArray | null;
      while ((match = /\r\n|\r|\n/.exec(buffer))) {
        if (!done && match[0] === '\r' && match.index === buffer.length - 1) break;
        const parsed = line(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
        if (parsed) yield parsed;
      }
      if (done) break;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
export async function answer(
  request: SearchRequest,
  callbacks: {
    sources: (event: SourcesEvent) => void;
    token: (text: string) => void;
    done: (event: DoneEvent) => void;
  },
  signal: AbortSignal,
) {
  const response = await fetch('/api/v1/answer', {
    method: 'POST',
    headers: {
      ...sessionHeaders(),
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ ...request, context_top_k: 5 }),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(response.status, error?.error?.message || response.statusText);
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream'))
    throw new Error('Invalid SSE response');
  for await (const event of parseSSE(response.body)) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError');
    if (event.event === 'sources') callbacks.sources(JSON.parse(event.data) as SourcesEvent);
    if (event.event === 'token')
      callbacks.token((JSON.parse(event.data) as Schemas['TokenEvent']).text);
    if (event.event === 'done') {
      callbacks.done(JSON.parse(event.data) as DoneEvent);
      return;
    }
    if (event.event === 'error') throw new Error((JSON.parse(event.data) as ErrorEvent).message);
  }
  throw new Error('Answer stream ended before completion');
}
