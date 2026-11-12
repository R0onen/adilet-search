# Integration guide

For a team that wants to call Adilet Search from its own backend (for example the Legal Service platform). The full API reference is `contracts/api.md`; the machine-readable schema is `contracts/openapi.json`, also served as Swagger UI at `/api/v1/docs`.

## Basics

- Base URL: `https://<host>/api/v1`. JSON in, JSON out, UTF-8.
- Every response has an `X-Request-Id` header. Log it: it finds the request in our logs.
- Every error has the same shape: `{"error": {"code", "message", "details", "request_id"}}`.
- Languages are `ru` and `kk`. `"lang": "auto"` (the default) detects the language of the query.

## Server-to-server calls

Ask the operator for an API key (it goes into `API_KEYS` on the server) and send it as `X-API-Key`. A valid key raises the rate limits 10× (600 searches and 100 answers per minute, counted per session + IP like the normal limits). Do not put the key into browser code.

If your backend calls on behalf of end users, also send a stable anonymous `X-Session-Id` per user (a random UUID you generate and keep). It groups a user's queries in the analytics and lets feedback overwrite an earlier vote. We store only a salted hash of it.

## Search

```bash
curl -s -X POST https://<host>/api/v1/search -H 'Content-Type: application/json' -H 'X-API-Key: <key>' -d '{"query": "Ответственность работодателя за задержку зарплаты", "top_k": 5}'
```

Python:

```python
import httpx

response = httpx.post(
    "https://<host>/api/v1/search",
    headers={"X-API-Key": API_KEY, "X-Session-Id": user_session},
    json={"query": question, "top_k": 5, "filters": {"doc_ids": ["K1500000414"]}},
    timeout=5.0,
)
response.raise_for_status()
for result in response.json()["results"]:
    print(result["article"]["article_id"], result["article"]["title"], result["article"]["url"])
```

PHP:

```php
$ch = curl_init('https://<host>/api/v1/search');
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT => 5,
    CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'X-API-Key: ' . $apiKey],
    CURLOPT_POSTFIELDS => json_encode(['query' => $question, 'top_k' => 5], JSON_UNESCAPED_UNICODE),
]);
$body = json_decode(curl_exec($ch), true);
foreach ($body['results'] as $result) {
    echo $result['article']['article_id'], ' ', $result['article']['title'], PHP_EOL;
}
```

What to use from a result: `article.article_id`, `article.number`, `article.title`, `article.url` (the official page on adilet.zan.kz), `doc.short_title`, `snippet` with `highlights`, `score`.

## Mapping results to your own documents

`article_id` is `{doc_id}:{lang}:{unit_key}`, for example `K1500000414:ru:a113`. `doc_id` is the document code of adilet.zan.kz (the Labor Code is `K1500000414`), so it matches any system that stores adilet codes. `GET /articles/{article_id}` returns the full text, the neighbouring articles and the same article in the other language (`parallel_article_id`).

## Streamed answers

`POST /answer` returns Server-Sent Events: `sources` once, then `token` many times, then `done` (or `error`). The text in `done` is final: replace the streamed text with it.

JavaScript (browser or Node 18+):

```js
const response = await fetch('https://<host>/api/v1/answer', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: question }),
});
const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
let buffer = '';
for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += value;
  const blocks = buffer.split(/\r?\n\r?\n/);
  buffer = blocks.pop();
  for (const block of blocks) {
    const event = /^event: (.+)$/m.exec(block)?.[1];
    const data = /^data: (.+)$/m.exec(block)?.[1];
    if (!event || !data) continue; // ": ping" heartbeats have neither
    const payload = JSON.parse(data);
    if (event === 'sources') showSources(payload.sources);
    if (event === 'token') appendText(payload.text);
    if (event === 'done') replaceText(payload.text, payload.citations);
    if (event === 'error') showError(payload.message);
  }
}
```

Python:

```python
import json
import httpx

with httpx.stream("POST", "https://<host>/api/v1/answer", json={"query": question}, timeout=120) as stream:
    event = None
    for line in stream.iter_lines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and event:
            payload = json.loads(line.split(":", 1)[1])
            if event == "done":
                print(payload["text"], payload["citations"])
```

`[n]` in the text refers to the source with `ref: n` in the `sources` event. Citations to anything else have already been removed. `grounded: false` means the answer cites nothing: show it with a warning or hide it.

## Timeouts, retries and failures

| Situation | What you get | What to do |
|---|---|---|
| Normal search | `200`, usually under 1 s | set a client timeout of 5 s |
| The semantic path is down | `200` with `degraded: ["semantic"]`, results from keyword search | show the results; they are less precise |
| The reranker was skipped | `200` with `degraded: ["rerank"]` | nothing |
| Too many requests | `429` with `Retry-After: <seconds>` | wait that long, then retry once |
| Everything is down | `503` | retry after 2 s, then 5 s; then fall back to your own search |
| Bad request | `422` with `details` per field | fix the request; do not retry |
| The LLM is down | the stream has `sources`, then `error` (`generation_unavailable`) | show the sources without an answer |

Queries are 1–500 characters; request bodies up to 64 KB. Do not retry `4xx` other than `429`.

## Feedback

`POST /feedback` with the `query_id` from a search or from the `sources` event, `target` (`result` or `answer`), `rating` (`1` or `-1`) and, for a result, its `article_id`. It feeds the satisfaction rate and the "negative feedback" filter in the admin panel.

## Ways to embed

1. **Link** to the hosted UI: `https://<host>/` for search, `https://<host>/?article=<article_id>` to open one article.
2. **Your own UI on our API** (this guide).
3. An `<iframe>` is **not** possible as shipped: the proxy sends `frame-ancestors 'none'`. To allow one site, change that directive in `infra/caddy/Caddyfile` to that site's origin.

## When the law changes

The corpus is a snapshot with a `corpus_version`. To update: rebuild the corpus files (`ml/scripts/download_data.py` for a new dataset release), then reindex from the admin panel or the CLI. The new index is built next to the old one and takes over when it is complete; `article_id`s of unchanged articles stay the same.
