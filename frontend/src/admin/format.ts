/** Pure helpers of the admin panel: kept apart from the components so they are easy to test. */

export type Tone = 'good' | 'warn' | 'bad' | 'neutral';

/** The search target is p95 <= 2 s: green up to 1.5 s, amber up to 2 s, red above. */
export function latencyTone(p95Ms: number | null | undefined): Tone {
  if (p95Ms === null || p95Ms === undefined) return 'neutral';
  if (p95Ms <= 1500) return 'good';
  return p95Ms <= 2000 ? 'warn' : 'bad';
}

export function percent(rate: number | null | undefined): string {
  return rate === null || rate === undefined ? '—' : `${(rate * 100).toFixed(1)}%`;
}

export function milliseconds(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value >= 1000 ? `${(value / 1000).toFixed(2)} с` : `${value} мс`;
}

export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** The last `days` UTC days, today included: the backend counts in UTC days too. */
export function lastDays(days: number, today = new Date()): { from: string; to: string } {
  const start = new Date(today);
  start.setUTCDate(start.getUTCDate() - (days - 1));
  return { from: isoDate(start), to: isoDate(today) };
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Drop empty values, so the URL holds only the filters that are set. */
export function compact(values: Record<string, string | undefined>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values).filter((entry): entry is [string, string] => !!entry[1]),
  );
}

export const DEGRADED_LABELS: Record<string, string> = {
  semantic: 'без семантики (полнотекстовый поиск)',
  rerank: 'без переранжирования',
  generation: 'без генерации ответа',
};
