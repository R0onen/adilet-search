import { describe, expect, it } from 'vitest';
import { parseSSE } from './sse';

const encoder = new TextEncoder();
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
