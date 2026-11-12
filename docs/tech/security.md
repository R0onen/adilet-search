# Security

What the system protects, how, and what is out of scope. The code is in `backend/app/core/` (`security.py`, `ratelimit.py`, `middleware.py`) and `backend/app/api/deps.py`.

## What is protected and how

| Area | Measure |
|---|---|
| Admin access | `POST /admin/login` checks a bcrypt hash and issues a JWT (HS256, 8 h). Every other `/admin/*` route requires it; a missing, malformed, expired or wrongly signed token gets `401`. The admin user is created at startup from `ADMIN_USERNAME` and `ADMIN_PASSWORD_HASH`; the password itself is never stored or configured. |
| Brute force on login | 5 attempts per minute per client. An unknown user and a wrong password give the same message and take the same time (a dummy hash is checked). |
| Secrets | Only in environment variables (`.env`, git-ignored). `ENVIRONMENT=prod` refuses to start with the development `SESSION_SALT` or `JWT_SECRET`. The LLM key is used only by the ML service and never reaches the browser. |
| Abuse and cost | Rate limits per session + IP: `/search` 60/min, `/answer` 10/min (each answer costs LLM tokens). `429` with `Retry-After`. Request bodies over 64 KB get `413`. Query length is capped at 500 characters. |
| Server-to-server callers | `X-API-Key` (keys in `API_KEYS`), compared in constant time; a valid key raises the limits 10×. |
| Personal data | Queries are logged for analytics (a product requirement), linked only to a salted HMAC of the anonymous `X-Session-Id`. No IP address, raw session id or full user agent is stored. The rate limiter keeps only a hash of IP + session, in memory, for one minute. |
| Injection | All SQL uses bound parameters (SQLAlchemy; the admin reporting queries too). Request bodies are validated by Pydantic models. The admin query filter treats `%` and `_` as plain characters. |
| Prompt injection through documents | The generator only sees statute text from our own corpus, never user-supplied documents. Citations to sources that were not provided are removed before the answer is shown. |
| Cross-origin requests | CORS allowlist (`CORS_ORIGINS`), no credentials, fixed methods and headers. |
| Error leakage | Every error has the contract shape; unhandled exceptions return a generic `500` with a request id, and details go only to the logs. |
| Internal endpoints | `/metrics` is served on the backend's own port and must not be routed by the reverse proxy. Postgres, Qdrant, the ML service, Prometheus and Grafana bind to `127.0.0.1` on the host. Grafana has anonymous access off. |
| Dependencies | Versions are locked (`uv.lock`). CI runs `pip-audit` on the locked runtime dependencies. |
| Containers | The backend and ML images run as a non-root user. |

## Out of scope / known limits

- **One admin role.** There are no per-user permissions and no audit trail of admin actions beyond `last_login_at`.
- **Token revocation.** A JWT stays valid until it expires (8 h). Changing `JWT_SECRET` invalidates all tokens.
- **Rate limits and caches are per process.** With several backend workers each keeps its own counters; a shared store (Redis) would be needed for exact limits.
- **TLS** is terminated by the reverse proxy in the production stack, not by the backend.
- **The LLM provider sees the question and the retrieved statute text.** With a hosted LLM, user questions leave the server. A self-hosted model avoids that.
- **Legal correctness.** The system is a search aid. It can retrieve or cite the wrong article; answers are not legal advice, and the UI says so.

## Operator checklist before exposing the service

1. Set `ENVIRONMENT=prod`, a random `SESSION_SALT` and `JWT_SECRET` (`openssl rand -hex 32`).
2. Create the admin hash: `docker compose exec backend python -m app.cli hash-password`. Put it in `.env` in single quotes.
3. Change `GRAFANA_ADMIN_PASSWORD` and `POSTGRES_PASSWORD`.
4. Set `CORS_ORIGINS` to the real site origin only.
5. Keep ports other than the reverse proxy's closed to the internet.
