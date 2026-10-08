# Adilet Search

Semantic search and source-cited answers over the legislation of the Republic of Kazakhstan, built as the AI module of **Legal Service** (Tehsnab Group, https://test.tehprof.kz/legal).

Course final project. Team: Daniil Talyzin, Yernur Kazhyakpar, Kuanysh Murat.

Three AI coding agents develop this repository: **ML**, **Backend** and **Frontend**. Each one is driven by a teammate. This README is for the humans.

## Start here

| File | What it is |
|---|---|
| [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | The master plan: scope, architecture, timeline, gates, deliverables. Everyone reads it. |
| [agents/README.md](agents/README.md) | How to run the three agents, and which prompt to send at each phase. |
| [contracts/](contracts/) | The interfaces between the three parts (public API, internal ML service, data schema). Changes follow a process. |
| [docs/status/](docs/status/) | One status file per agent. This is the agents' shared memory and their handoff channel. |
| [docs/decisions.md](docs/decisions.md) | Decision log: why we chose what we chose. It feeds the "model selection rationale" parts of the reports. |
| [CLAUDE.md](CLAUDE.md) | Shared rules that every agent loads automatically. |

## Before the first agent session (one-time, ~1 hour)

1. **Move the repo** out of OneDrive and out of any path with Cyrillic characters, for example to `C:\dev\adilet-search` or, better, into WSL2 (`~/adilet-search`). OneDrive will try to sync `node_modules`, virtualenvs and multi-GB model files, and several Python/Node tools break on non-ASCII paths.
2. Run `git init`, create a **private** GitHub repo, push this skeleton to `main`, and invite the two teammates.
3. Install Docker Desktop (WSL2 backend), Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js LTS (22+), Git and Claude Code.
4. Create accounts:
   - **Hugging Face:** a shared org/namespace for private models and datasets, with one write token per person.
   - **Google Colab and/or Kaggle:** free GPUs for training.
   - **GitHub.**
5. ~~Ask Tehsnab Group for a DB export and a test VM.~~ Settled: they provide neither (decision D-012). We scrape adilet.zan.kz and rent our own VPS.
6. Fill in the owner names and gate dates in `docs/PROJECT_PLAN.md` §10.
7. Follow [agents/README.md](agents/README.md) to start the agents.

## Repository layout

See `docs/PROJECT_PLAN.md` §5. Until the agents scaffold their parts, only the planning files exist:

```
CLAUDE.md, README.md, .gitignore
docs/      PROJECT_PLAN.md, decisions.md, status/
contracts/ api.md, ml_service.md, data_schema.md, CHANGELOG.md
agents/    README.md, ml/, backend/, frontend/, shared/
```
