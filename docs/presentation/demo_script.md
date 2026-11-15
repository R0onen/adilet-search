# Demo script (about 3 minutes)

The demo runs against the deployed configuration: pipeline 1.0.0, 40 acts, generated answers from the hosted LLM. Questions with their expected articles are in `demo_questions.md`.

## Where to open it

- Public: the URL in the README (after deployment).
- Local: http://localhost:8080 with `docker compose -f docker-compose.prod.yml up -d` (see `docs/tech/deployment.md`). Docker Desktop must be running.
- Admin panel: `/admin`, with the admin account from `.env`.
- Grafana: `/grafana` behind the proxy.

## Steps

| # | Do | Say |
|---|---|---|
| 1 | Type «работодатель задерживает зарплату — что делать?» and search | The question has none of the statute's words. Article 113 of the Labor Code, "Порядок и сроки выплаты заработной платы", is first: everyday words are expanded into legal terms, dense and keyword search are fused, and our fine-tuned reranker orders the top. |
| 2 | Press the answer button | The LLM gets only the retrieved articles. The answer arrives as a stream and every statement carries a citation: the employer owes the wage and a penalty for each day of delay. The articles do not say what the worker should do next, and the answer says that too instead of inventing it. |
| 3 | Click a citation `[1]` | The article opens with its official text, stored verbatim. This is the evidence; the answer is an explanation of it. |
| 4 | In the article, switch to Kazakh | The parallel Kazakh article is linked. |
| 5 | Ask «можно ли вернуть товар в магазин без чека» and request the answer | A direct answer ("yes, if the purchase can be proved") from the Consumer Protection Law, one of the 32 acts added to the 8 codes. |
| 6 | Ask «сколько могут держать мой телефон в вещдоке» and request the answer | No article gives a time limit for this. The answer says so first, then reports what the articles on material evidence do say. |
| 7 | Switch the source language to Kazakh, ask «Жұмыс уақытының қалыпты ұзақтығы қандай?» | Article 68 of the Labor Code in Kazakh. |
| 8 | Open `/compare` with any question | Keyword search and hybrid search side by side. |
| 9 | Open `/admin` | Usage statistics, the query log with latency and degradation marks, health, reindexing. |

## If something fails

- **The answer fails with an error.** The hosted LLM's free tier allows 8,000 tokens a minute (about two answers) and 200,000 a day (about 50 answers). The service waits and retries once; if it still fails, wait a minute. Do not spend the daily budget on rehearsals on the day of the defence. Search does not depend on the LLM.
- **Results are marked as keyword-only.** The ML service or the vector index is down and search fell back to PostgreSQL full-text search. Say so; this is the designed behaviour. `docker compose -f docker-compose.prod.yml ps` shows which container is unhealthy.
- **The first search after a restart is slow.** The models are loading; repeat it.
- **Nothing opens.** Use the backup recording.

## What not to claim

- The numbers on the slides are from LLM-written test questions, 60 of them checked by a person. Not from lawyers.
- A valid citation shows where a statement comes from. It does not prove the statement is right.
- The corpus is a snapshot of 17 September 2026.
