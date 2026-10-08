# Adilet Search — shared rules for all agents

Adilet Search adds semantic search and source-cited answers (RAG) over Kazakhstan legislation to the Legal Service platform. Three agents build it: **ML**, **Backend** and **Frontend**. The master plan is `docs/PROJECT_PLAN.md`; read it before you do anything else in a new session. Your role brief is `agents/<role>/00_general.md`.

## Who owns what

| Path | Owner |
|---|---|
| `ml/`, `data/`, `contracts/data_schema.md`, `contracts/ml_service.md`, `contracts/fixtures/` | ML |
| `backend/`, `infra/`, `docker-compose*.yml`, `.env.example`, `.github/workflows/`, `contracts/api.md`, `contracts/openapi.json` | Backend |
| `frontend/` | Frontend |
| `docs/status/<role>.md` | that role |
| `docs/decisions.md`, `contracts/CHANGELOG.md` | shared, append-only (never rewrite another agent's entry) |
| `docs/tech/`, `docs/report/`, `docs/presentation/` | shared; each agent edits only the files assigned to it in its brief |

Everyone may read everything. **Never edit files owned by another agent.** If you need a change there, add it under "Requests to other agents" in your status file and tell the human, who relays it.

## Contracts

- `contracts/` is the source of truth for every interface between the parts. Code follows the contracts, not the other way round.
- To change a contract:
  1. edit the contract file you own;
  2. append an entry to `contracts/CHANGELOG.md` (date, what changed, why, breaking yes/no, who must react);
  3. note it in your status file;
  4. tell the human so they can relay it.
- A breaking change needs an OK from the affected owner first.
- `contracts/openapi.json` is generated from the backend code and never hand-edited. The frontend generates its TypeScript types from it.

## Status files are the shared memory

At the end of every phase, and before you stop for the day, update `docs/status/<role>.md`: Current phase, Done, In progress, Next steps, Blockers, Requests to other agents, Notes for others. Keep it short and current. It is how a fresh session (yours or another agent's) picks up context.

## Engineering rules (all parts)

- **Paths and config.** No hard-coded absolute or machine-specific paths. Resolve paths from the repo root or from env vars. Config comes from env vars (`.env`, documented in `.env.example`).
- **Secrets.** Never commit secrets. Tokens go in `.env` (git-ignored) or in Colab/Kaggle secrets.
- **Reproducibility.** Pin dependency versions (uv lockfiles, package-lock.json). Fix random seeds in anything stochastic.
- **Tests.** Every change ships with tests, or with a stated reason why not. Don't leave the build red.
- **Git workflow.**
  - Small commits using Conventional Commits with a scope: `feat(ml): …`, `fix(be): …`, `test(fe): …`.
  - One branch per phase: `ml/03-baseline`, `be/02-search`, `fe/04-admin`.
  - Open a PR to `main`; a human merges it.
  - At the start of each phase, run `git pull --rebase origin main`.
- **Language.**
  - Code, identifiers, comments and docs are in English.
  - UI text is Russian (default), Kazakh and English, via i18n.
  - Legal texts are stored and shown verbatim. Never paraphrase or "fix" statute text.
  - Language codes are ISO 639-1: `ru` and `kk` (not `kz`).
- **Honest results.** Report only numbers produced by code in this repo, negative results included. If a number comes from synthetic queries, say so.
- **Plan first.** Before you write code in a new phase, reply with a short plan and the questions a human must answer. Then proceed.
- **End every phase** with a reply that covers three things:
  1. what was done;
  2. how to verify it (exact commands);
  3. what the other agents need to know.

## Things you cannot do yourself

- GPU training runs on Colab/Kaggle, not here. Prepare the notebook or script, smoke-test it on CPU with a few steps, then ask the human to run it and commit the resulting `ml/experiments/<run_id>/` folder.
- Accounts, tokens, purchases (VPS, domain), messages to the customer, and labelling of the gold set are done by humans. Ask for them explicitly.

## Environment

Developers use Windows with WSL2 and Docker Desktop. Shell commands in docs must work in bash (WSL2, Linux, macOS, Git Bash). Use forward slashes and relative paths.
