import { describe, expect, it } from 'vitest';
import { mockSearch } from './handlers';

describe('synthetic demo retrieval', () => {
  it('finds a plain-language salary query without pretending keyword search understands it', () => {
    const request = { query: 'Мне не платят зарплату', lang: 'ru' as const, top_k: 10 };
    const smart = mockSearch({ ...request, mode: 'hybrid' });
    const keyword = mockSearch({ ...request, mode: 'keyword' });
    expect(smart.results[0].article.article_id).toBe('T0000000001:ru:a114');
    expect(keyword.results.length).toBeLessThan(smart.results.length);
    expect(smart.pipeline_version).toBe('synthetic-demo');
    expect(smart.timing_ms.total).toBeUndefined();
  });
  it('detects Kazakh and excludes repealed or excluded provisions by default', () => {
    const result = mockSearch({
      query: 'Жалақымды төлемейді',
      lang: 'auto',
      mode: 'hybrid',
      top_k: 10,
    });
    expect(result.lang).toBe('kk');
    expect(result.results.length).toBeGreaterThan(0);
    expect(
      result.results.every(
        (item) =>
          item.lang === 'kk' &&
          item.doc.status === 'in_force' &&
          item.article.unit_status === 'in_force',
      ),
    ).toBe(true);
  });
  it('respects filters and returns an honest empty result', () => {
    expect(
      mockSearch({
        query: 'зарплата',
        lang: 'ru',
        mode: 'hybrid',
        top_k: 10,
        filters: { doc_ids: ['T0000000002'], in_force_only: true },
      }).results,
    ).toEqual([]);
    expect(
      mockSearch({ query: 'астрономия галактика', lang: 'ru', mode: 'hybrid', top_k: 10 }).results,
    ).toEqual([]);
  });
});
