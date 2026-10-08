// Original diagnostic questions, not a human-labelled benchmark or training data.
/* global process, fetch, console, AbortSignal */
import { writeFile, mkdir } from 'node:fs/promises';
const api = process.env.API_BASE || 'http://127.0.0.1:18000/api/v1';
const labor = 'K1500000414',
  eco = 'K2100000400';
const cases = [
  {
    id: 'hours-direct',
    type: 'direct',
    lang: 'ru',
    query: 'Какова нормальная продолжительность рабочего времени в неделю?',
    needs: [[labor, '68']],
  },
  {
    id: 'leave-direct',
    type: 'direct',
    lang: 'ru',
    query: 'Какова продолжительность основного оплачиваемого ежегодного трудового отпуска?',
    needs: [[labor, '88']],
  },
  {
    id: 'pay-direct',
    type: 'direct',
    lang: 'ru',
    query:
      'Какие сроки выплаты заработной платы? Что происходит, если день выплаты совпадает с выходным?',
    needs: [[labor, '113']],
  },
  {
    id: 'pay-paraphrase',
    type: 'paraphrase',
    lang: 'ru',
    query:
      'Начальник уже две недели не переводит деньги за прошлый месяц. Кроме самого долга, положена ли мне компенсация за ожидание?',
    needs: [[labor, '113']],
  },
  {
    id: 'overtime-multipart',
    type: 'multipart',
    lang: 'ru',
    query:
      'Каковы пределы сверхурочной работы и как она оплачивается? Требуется ли письменное согласие работника?',
    needs: [
      [labor, '77'],
      [labor, '78'],
      [labor, '108'],
    ],
  },
  {
    id: 'overtime-paraphrase',
    type: 'paraphrase',
    lang: 'ru',
    query:
      'Меня каждый день оставляют после смены ещё на три часа. Можно ли так делать постоянно и должны ли платить больше обычного?',
    needs: [
      [labor, '78'],
      [labor, '108'],
    ],
  },
  {
    id: 'leave-recall',
    type: 'multipart',
    lang: 'ru',
    query:
      'Может ли работодатель отозвать меня из ежегодного оплачиваемого отпуска без моего согласия? Что происходит с неиспользованной частью?',
    needs: [[labor, '95']],
  },
  {
    id: 'childcare',
    type: 'paraphrase',
    lang: 'ru',
    query:
      'Хочу сидеть дома с ребёнком до его трёхлетия. Сохранится ли моё рабочее место и можно ли выйти раньше?',
    needs: [[labor, '100']],
  },
  {
    id: 'hours-kk',
    type: 'direct',
    lang: 'kk',
    query: 'Жұмыс уақытының қалыпты ұзақтығы аптасына қанша сағат?',
    needs: [[labor, '68']],
  },
  {
    id: 'leave-kk',
    type: 'direct',
    lang: 'kk',
    query: 'Жыл сайынғы ақы төленетін негізгі еңбек демалысының ұзақтығы қандай?',
    needs: [[labor, '88']],
  },
  {
    id: 'information',
    type: 'multipart',
    lang: 'ru',
    query:
      'Как получить доступ к экологической информации? В какие сроки должны предоставить ответ на запрос?',
    needs: [
      [eco, '18'],
      [eco, '20'],
    ],
  },
  {
    id: 'information-paraphrase',
    type: 'paraphrase',
    lang: 'ru',
    query:
      'Возле дома завод, хочу узнать, чем мы дышим. Могу ли я запросить данные о загрязнении, даже если не объясню, зачем они мне?',
    needs: [[eco, '18']],
  },
  {
    id: 'hearings',
    type: 'direct',
    lang: 'ru',
    query:
      'Как проводятся общественные слушания по проекту отчёта о возможных воздействиях на окружающую среду?',
    needs: [[eco, '73']],
  },
  {
    id: 'tax-unsupported',
    type: 'unsupported',
    lang: 'ru',
    query: 'Какова ставка НДС в Казахстане в 2026 году и кто обязан платить этот налог?',
    needs: [],
  },
  {
    id: 'criminal-unsupported',
    type: 'unsupported',
    lang: 'ru',
    query: 'Какое уголовное наказание предусмотрено за кражу телефона?',
    needs: [],
  },
];
const report = {
  at: new Date().toISOString(),
  scope: 'two-code diagnostic; author-inferred source labels, no benchmark claim',
  cases: [],
};
await mkdir('test-results', { recursive: true });
for (const item of cases) {
  const response = await fetch(`${api}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: item.query, lang: item.lang, top_k: 10 }),
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Search ${response.status}`);
  const data = await response.json();
  const ids = data.results.map((r) => r.article.article_id);
  const ranks = item.needs.map(([doc, n]) => {
    const pos = ids.indexOf(`${doc}:${item.lang}:a${n}`);
    return pos < 0 ? null : pos + 1;
  });
  const row = {
    ...item,
    sourceRanks: ranks,
    allRequiredTop5: ranks.length ? ranks.every((r) => r !== null && r <= 5) : null,
    allRequiredTop10: ranks.length ? ranks.every((r) => r !== null) : null,
    results: data.results.map((r) => ({ id: r.article.article_id, title: r.article.title })),
    timing: data.timing_ms,
  };
  report.cases.push(row);
  console.log(JSON.stringify({ id: row.id, ranks, top: ids[0], allTop5: row.allRequiredTop5 }));
}
report.summary = {
  supported: report.cases.filter((c) => c.needs.length).length,
  allRequiredTop5: report.cases.filter((c) => c.allRequiredTop5).length,
  allRequiredTop10: report.cases.filter((c) => c.allRequiredTop10).length,
};
await writeFile('test-results/baseline-retrieval.json', JSON.stringify(report, null, 2));
console.log(JSON.stringify(report.summary));

if (process.argv.includes('--answers')) {
  const selection = process.env.EVAL_CASES?.split(',') || [
    'pay-paraphrase',
    'overtime-multipart',
    'leave-recall',
    'information',
    'tax-unsupported',
  ];
  for (const item of report.cases.filter((c) => selection.includes(c.id))) {
    // Sequential: do not exhaust a free API with a parallel burst.
    const response = await fetch(`${api}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: item.query, lang: item.lang, context_top_k: 5 }),
      signal: AbortSignal.timeout(100000),
    });
    const text = await response.text();
    const events = text
      .replace(/\r\n/g, '\n')
      .split('\n\n')
      .flatMap((block) => {
        const name = block.match(/^event: (.+)$/m)?.[1],
          payload = block.match(/^data: (.+)$/m)?.[1];
        return name && payload ? [{ name, data: JSON.parse(payload) }] : [];
      });
    item.answer = {
      done: events.find((e) => e.name === 'done')?.data,
      error: events.find((e) => e.name === 'error')?.data,
      sources: events
        .find((e) => e.name === 'sources')
        ?.data.sources.map((s) => ({ ref: s.ref, id: s.article.article_id })),
    };
    console.log(JSON.stringify({ id: item.id, answer: item.answer }));
    await writeFile('test-results/baseline-answers.json', JSON.stringify(report, null, 2));
  }
}
