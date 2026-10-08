# BE-06: Deployment to an accessible environment (week 6)

**Goal: G5.** The prototype runs at a public HTTPS URL, with monitoring, backups and a runbook.

**Ask the human first:**
- Has the team rented the VPS yet (Ubuntu 24.04, ≥ 4 vCPU / 16 GB RAM / 80 GB SSD)? The customer provides no VM (D-012).
- The domain, or a customer subdomain.
- SSH access.
- Generator mode for demo day: the CPU GGUF on the VM, or an external GPU endpoint (`LLM_BASE_URL`)?

## Tasks

1. **`docker-compose.prod.yml`:**
   - `caddy`:
     - automatic HTTPS;
     - `/` → `frontend:8080`, `/api/*` → `backend:8000`, `/grafana/*` → `grafana:3000`;
     - security headers (HSTS, `X-Content-Type-Options`, `Referrer-Policy`, a CSP agreed with Frontend);
     - gzip/zstd.
   - `backend` (gunicorn with uvicorn workers, sized to the CPU), `ml-service`, `llm` (profile `llm-cpu`), `postgres`, `qdrant`, `prometheus`, `grafana`.
   - **Only 80/443 are published.** Everything else stays on the internal network.
   - Resource limits per service, from the measured RAM. Log rotation (the json-file driver with max-size).
   - Pinned image tags (no `latest`).

2. **Server bootstrap**, written up as `docs/tech/deployment.md` and `scripts/bootstrap_server.sh`:
   - Docker, a non-root deploy user, ufw (22/80/443 only), fail2ban, unattended-upgrades;
   - clone the repo;
   - create `.env` from `.env.example` (strong secrets, the `ADMIN_PASSWORD_HASH`, `JWT_SECRET`, the salts);
   - download the models per the manifest and the corpus per `corpus_version`;
   - `alembic upgrade head`;
   - run the indexer with the precomputed embeddings;
   - `docker compose -f docker-compose.prod.yml up -d`;
   - run `scripts/smoke.sh https://<domain>`.

3. **Deploy procedure** `scripts/deploy.sh`: pull → build → migrate → `up -d` → smoke test → print the version. A rollback section covers the previous git tag and the previous Qdrant collection (an alias switch). Optionally a GitHub Actions deploy job over SSH, run manually.

4. **Backups:**
   - a nightly `pg_dump` (keep 7 days);
   - a Qdrant snapshot after every reindex;
   - both stored in a backup volume, with the commands to copy them off the server documented;
   - **restore once on a scratch stack** and record that it worked.

5. **Monitoring in production.**
   - Grafana is behind its own login.
   - Prometheus retention is 15 days.
   - Optionally an external uptime check (e.g. UptimeRobot, free tier) on `/api/v1/health`. Note its URL in the runbook.

6. **Runbook** `docs/tech/runbook.md` (written for whoever is on duty during the defence):
   - start/stop and logs;
   - how to check health;
   - reindex;
   - rolling back a model (switch the alias back) and rolling back the app (previous tag);
   - rotating secrets;
   - switching `LLM_BASE_URL` between CPU and GPU;
   - what to do if: the ML service OOMs, the disk fills up, a TLS certificate fails, the LLM is slow.

7. **Post-deploy checks:**
   - run `scripts/smoke.sh`;
   - a short locust run (10 users, 3 min) against production, results appended to `docs/report/load_test.md`;
   - the degraded drill on production (stop `ml-service` for 1 minute; search stays up);
   - give ML the URL for `eval_api.py`.

## Acceptance criteria (G5)

- [ ] `https://<domain>` serves the UI. `/api/v1/health` reports `ok` with the v1.0.0 pipeline.
- [ ] Grafana is reachable with a login and shows production traffic. Screenshots are in `docs/presentation/img/`.
- [ ] Backup and restore were tested. The runbook is complete. The URL and credentials process are recorded (credentials go to the team privately, never in git).
- [ ] Every agent's status file has the URL.
