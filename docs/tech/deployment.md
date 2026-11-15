# Deployment

The production stack is `docker-compose.prod.yml`: a Caddy reverse proxy in front of the UI, the backend, the ML service, Postgres, Qdrant, Prometheus and Grafana. Only ports 80 and 443 are published.

**Status:** the stack has been verified locally over plain HTTP (see "Local check"). It has not been deployed to a public server: the team has no VPS or domain yet. The steps below are what to do when there is one.

## What you need

- A server with Ubuntu 24.04, at least 4 vCPU, 16 GB RAM and 40 GB of free disk. The ML service needs about 3 GB of RAM for the two models; indexing the corpus on CPU takes about 45 minutes.
- A domain name whose A record points to the server (needed for automatic HTTPS).
- An API key for an OpenAI-compatible LLM (for generated answers), or accept the extractive fallback.

## First deployment

1. Install Docker and open only ports 22, 80 and 443:

   ```bash
   curl -fsSL https://get.docker.com | sh && sudo ufw allow 22 && sudo ufw allow 80 && sudo ufw allow 443 && sudo ufw enable
   ```

2. Get the code and create `.env`:

   ```bash
   git clone https://github.com/R0onen/adilet-search.git && cd adilet-search && cp .env.example .env
   ```

3. Edit `.env`. The production stack refuses to start without these:

   | Variable | Value |
   |---|---|
   | `SITE_ADDRESS` | the domain, e.g. `search.example.kz` (Caddy then gets a certificate by itself) |
   | `ACME_EMAIL` | an e-mail for certificate notices |
   | `CORS_ORIGINS` | `https://<domain>` |
   | `POSTGRES_PASSWORD` | a random password |
   | `SESSION_SALT`, `JWT_SECRET` | `openssl rand -hex 32`, one each |
   | `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` | the admin login; make the hash in step 5 and keep it in single quotes |
   | `GRAFANA_ADMIN_PASSWORD` | a random password |
   | `ADILET_ML_GENERATOR_MODE`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | the LLM (see `backend/README.md`) |
   | `ML_MODEL_MANIFEST_PATH` | `/app/models/model_manifest.ft.json` for pipeline 1.0.0 (the fine-tuned reranker). Its weights are not in git: copy the folder `ml/models/checkpoints/reranker-ft-written/` to the same path on the server first. Leave the variable out to run the pretrained pipeline 0.2.0. |

4. Build the corpus files (downloads the public AdiletCodex dataset, 34 MB, and verifies it). `--tier 2` is the curated set of 40 acts; without it only the 8 main codes are built:

   ```bash
   docker run --rm -v "$PWD":/repo -w /repo/ml python:3.12-slim sh -c "pip install -q . && python scripts/download_data.py --tier 2"
   ```

5. Make the admin password hash and put it into `.env`:

   ```bash
   docker compose -f docker-compose.prod.yml run --rm --no-deps backend python -m app.cli hash-password
   ```

6. Start everything. The first start downloads the model weights (about 1.6 GB):

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

7. Get an index. Either copy a finished one from a machine that has it (minutes), or build it on the server (hours on CPU; search answers from the full-text fallback meanwhile).

   Copy: on the machine with the index run `scripts/transfer_index.sh export ./index_export`, copy the folder to the server, then on the server: The export of the 40-act index is about 315 MB (a 300 MB Qdrant snapshot and a 12 MB database dump).

   ```bash
   scripts/transfer_index.sh import ./index_export
   ```

   Build:

   ```bash
   docker compose -f docker-compose.prod.yml exec backend python -m indexer --data-dir /data/processed
   ```

8. Check the deployment:

   ```bash
   scripts/smoke.sh https://<domain>
   ```

## Updating

```bash
git pull && docker compose -f docker-compose.prod.yml up -d --build && scripts/smoke.sh https://<domain>
```

Database migrations run automatically (the `migrate` service) before the backend starts. If the release notes say that `index_compat_id` changed, run step 7 again; the old index keeps serving through the full-text fallback until the new one is ready.

## Backups

`scripts/backup.sh` writes a Postgres dump to the `backups` volume (7 days are kept) and makes a snapshot of the live Qdrant collection. Run it nightly:

```bash
(crontab -l 2>/dev/null; echo "15 2 * * * cd $PWD && scripts/backup.sh >> backup.log 2>&1") | crontab -
```

Copy a dump off the server with `scripts/backup.sh --copy ./out` and `scp`. The Qdrant index can always be rebuilt from the corpus (step 7), so the Postgres dump (query logs, feedback, admin user) is the part that cannot be recreated.

## Local check

The same stack runs on a laptop over plain HTTP, next to nothing else on ports 8080/8443. It uses the same Docker volumes as the dev stack (same project name), so an existing index and the downloaded models are reused. Stop the dev stack first (`docker compose --profile ml down`, without `-v`).

```bash
SITE_ADDRESS=:80 HTTP_PORT=8080 HTTPS_PORT=8443 CORS_ORIGINS=http://localhost:8080 GRAFANA_ADMIN_PASSWORD=admin docker compose -f docker-compose.prod.yml up -d --build
```

```bash
scripts/smoke.sh http://localhost:8080
```

`POSTGRES_PASSWORD`, `SESSION_SALT`, `JWT_SECRET` and the admin login must be in `.env`. The UI is then at `http://localhost:8080`, the admin panel at `/admin`, Grafana at `/grafana/`.

## Known limits

- **One backend process.** The rate limiter and the cache are per process, so the backend runs a single worker. It is I/O-bound (the models run in the ML service), which is enough for the measured load (`docs/report/load_test.md`).
- **CPU only.** The embedder and the reranker run on CPU. A GPU would cut indexing from about 45 minutes to a few.
- **Free-tier LLM.** A hosted free tier limits tokens per day; when it is exhausted, answers fail with `generation_unavailable` while search keeps working.
