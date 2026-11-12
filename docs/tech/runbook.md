# Runbook

For whoever looks after the running system. Commands are for the production stack; set this first:

```bash
export DC="docker compose -f docker-compose.prod.yml"
```

For the dev stack use `docker compose --profile ml` instead.

## Start, stop, logs

| Task | Command |
|---|---|
| Start / update | `$DC up -d --build` |
| Stop (data is kept) | `$DC stop` |
| State of every service | `$DC ps` |
| Logs of one service | `$DC logs -f --tail 200 backend` (or `ml-service`, `caddy`, …) |
| One request in the logs | every response has an `X-Request-Id`; `$DC logs backend \| grep <id>` |

Never run `down -v`: `-v` deletes the database, the index and the downloaded models.

## Is it healthy?

1. `scripts/smoke.sh https://<domain>` checks health, search in both languages, an article, an answer and the admin protection.
2. `https://<domain>/api/v1/health`: `ok`, `degraded` (search works, something is down) or `down` (Postgres is down).
3. The admin panel, page "Система": components, models, index, last reindex.
4. Grafana at `/grafana/`: latency per stage, errors, degraded responses.

## What the user sees when something fails

| Failure | Effect | What to do |
|---|---|---|
| ML service down or still loading | search answers from the full-text fallback (`degraded: ["semantic"]`); answers use those sources | `$DC logs ml-service`; `$DC restart ml-service`. It needs up to 5 minutes to load the models. |
| Qdrant down | same as above | `$DC restart qdrant` |
| Reranker slow (over 1.5 s) | results in fused order (`degraded: ["rerank"]`) | lower `SEARCH_RERANK_TOP_N` in `.env` (for example 10), then `$DC up -d backend` |
| LLM down or daily quota used up | sources are shown; the answer panel shows an error | check the key and the quota; switch `LLM_MODEL` or `LLM_BASE_URL` in `.env`, then `$DC up -d ml-service` |
| Postgres down | `503` everywhere | `$DC logs postgres`; `$DC restart postgres` |
| "Требуется переиндексация" in the admin panel | search is on the full-text fallback | reindex (below) |

## Reindex

From the admin panel (page "Система" → "Переиндексировать"), or:

```bash
$DC exec backend python -m indexer --data-dir /data/processed
```

A new collection is built next to the live one and the alias moves only on success, so search is never interrupted. If an indexer run was killed (crash, restart) and the next run says "another index job is queued or running", add `--abandon-stuck-job`.

## Roll back

- **The application:** `git checkout <previous tag or commit> && $DC up -d --build`.
- **The index** (after a bad reindex): old collections are kept. List them and point the alias back:

  ```bash
  $DC exec backend python -c "import json,urllib.request; print([c['name'] for c in json.load(urllib.request.urlopen('http://qdrant:6333/collections'))['result']['collections']])"
  ```

  ```bash
  $DC exec backend python -c "import json,urllib.request; body=json.dumps({'actions':[{'delete_alias':{'alias_name':'legal_chunks'}},{'create_alias':{'collection_name':'<COLLECTION>','alias_name':'legal_chunks'}}]}).encode(); print(urllib.request.urlopen(urllib.request.Request('http://qdrant:6333/collections/aliases', data=body, headers={'Content-Type':'application/json'})).read())"
  ```

  The collection must have been built with the models that are running now (same `index_compat_id`), otherwise search stays on the fallback.

## Backups and restore

- Back up: `scripts/backup.sh` (nightly from cron, see `deployment.md`).
- **Restore from a backup** (Postgres):

  ```bash
  $DC stop backend && $DC exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /backups/<file>.dump' && $DC start backend
  ```

- The index is rebuilt from the corpus with a reindex; it does not need to be restored.

## Secrets

- **Change the admin password:** make a new hash (`$DC exec backend python -m app.cli hash-password`), put it in `.env` as `ADMIN_PASSWORD_HASH='…'`, then `$DC up -d backend`.
- **Log every admin out:** change `JWT_SECRET`, then `$DC up -d backend`.
- **LLM key leaked:** revoke it at the provider, put the new one in `.env`, then `$DC up -d ml-service`.
- `.env` is never committed.

## Other problems

- **The disk is full:** `docker system df`; remove unused images with `docker image prune -a`. Logs are capped at 100 MB per service. Old Qdrant collections can be deleted once the current index is known to be good.
- **The ML service is killed (out of memory):** it needs about 3 GB. Check `$DC ps` (it restarts by itself) and the memory limit in `docker-compose.prod.yml`; lower `ADILET_ML_BATCH_SIZE` if it happens during indexing.
- **The certificate fails:** the domain's A record must point to the server and ports 80 and 443 must be open; then `$DC logs caddy`.
- **Too many `429`:** raise `RATE_LIMIT_SEARCH` / `RATE_LIMIT_ANSWER` in `.env`, or give the integration an `X-API-Key` (`API_KEYS`).
