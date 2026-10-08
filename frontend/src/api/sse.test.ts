import { afterEach, describe, expect, it, vi } from 'vitest';
import { answer, parseSSE } from './sse';
import { ApiError } from './client';

const encoder = new TextEncoder();
afterEach(() => vi.restoreAllMocks());
function stream(chunks: Uint8Array[]) {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(chunk));
      controller.close();
    },
  });
}
async function collect(chunks: Uint8Array[]) {
  const events = [];
  for await (const event of parseSSE(stream(chunks))) events.push(event);
  return events;
}
describe('POST-SSE parser', () => {
  it('preserves split UTF-8 characters, fields and CRLF boundaries', async () => {
    const bytes = encoder.encode(
      ': ping\r\nevent: token\r\ndata: {"text":"Жалақы"}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n',
    );
    const events = await collect([...bytes].map((byte) => new Uint8Array([byte])));
    expect(events).toEqual([
      { event: 'token', data: '{"text":"Жалақы"}' },
      { event: 'done', data: '{}' },
    ]);
  });
  it('handles several events and multiline data in one chunk', async () => {
    expect(
      await collect([
        encoder.encode(
          'event: sources\ndata: {}\n\nevent: error\ndata: {\ndata: "message":"offline"}\n\n',
        ),
      ]),
    ).toEqual([
      { event: 'sources', data: '{}' },
      { event: 'error', data: '{\n"message":"offline"}' },
    ]);
  });
  it('does not dispatch an incomplete event', async () => {
    expect(await collect([encoder.encode('event: token\ndata: {}')])).toEqual([]);
  });
  it('cancels the reader when the consumer stops', async () => {
    let cancelled = false;
    const source = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('event: token\ndata: {}\n\n'));
      },
      cancel() {
        cancelled = true;
      },
    });
    for await (const event of parseSSE(source)) {
      expect(event.event).toBe('token');
      break;
    }
    expect(cancelled).toBe(true);
  });
});

describe('answer stream lifecycle', () => {
  const request = { query: 'demo', lang: 'ru' as const, mode: 'hybrid' as const, top_k: 5 };
  const callbacks = () => ({ sources: vi.fn(), token: vi.fn(), done: vi.fn() });

  it.each([422, 503])('maps a JSON %s before the stream to ApiError', async (status) => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { message: 'Service rejected request' } }), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const listener = callbacks();
    await expect(answer(request, listener, new AbortController().signal)).rejects.toMatchObject({
      name: 'ApiError',
      status,
      message: 'Service rejected request',
    } satisfies Partial<ApiError>);
    expect(listener.sources).not.toHaveBeenCalled();
  });

  it('keeps already delivered sources when the generator sends an error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        'event: sources\r\ndata: {"sources":[]}\r\n\r\nevent: error\r\ndata: {"code":"generation_unavailable","message":"Generator unavailable"}\r\n\r\n',
        { headers: { 'Content-Type': 'text/event-stream' } },
      ),
    );
    const listener = callbacks();
    await expect(answer(request, listener, new AbortController().signal)).rejects.toThrow(
      'Generator unavailable',
    );
    expect(listener.sources).toHaveBeenCalledWith({ sources: [] });
    expect(listener.done).not.toHaveBeenCalled();
  });

  it('delivers final authoritative text separately from provisional tokens', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        'event: token\ndata: {"text":"provisional [99]"}\n\nevent: done\ndata: {"text":"final [1]","grounded":true}\n\n',
        { headers: { 'Content-Type': 'text/event-stream' } },
      ),
    );
    const listener = callbacks();
    await answer(request, listener, new AbortController().signal);
    expect(listener.token).toHaveBeenCalledWith('provisional [99]');
    expect(listener.done).toHaveBeenCalledWith({ text: 'final [1]', grounded: true });
  });

  it('rejects a stream that closes without done', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('event: token\ndata: {"text":"partial"}\n\n', {
        headers: { 'Content-Type': 'text/event-stream' },
      }),
    );
    await expect(answer(request, callbacks(), new AbortController().signal)).rejects.toThrow(
      'Answer stream ended before completion',
    );
  });
});
