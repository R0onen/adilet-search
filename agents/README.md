# Running the three agents

Three Claude Code sessions build Adilet Search, one per area:

| Agent | Standing brief | Phase prompts | Owns |
|---|---|---|---|
| **ML** | `ml/00_general.md` | `ml/01…07` | corpus, eval data, experiments (A2–A4), ml-service, model manifest |
| **Backend** | `backend/00_general.md` | `backend/01…07` | API, orchestration, DBs, admin API, monitoring, CI, deployment |
| **Frontend** | `frontend/00_general.md` | `frontend/01…07` | search UI, answer panel, article viewer, compare page, admin panel |

The **standing brief** (`00_general.md`) is the general prompt: role, mission, ownership, rules. The agent keeps following it for the whole session. **Phase prompts** are the follow-up instructions, sent one at a time when the previous phase is accepted.

---

## 1. Setup

**Option A (recommended): three teammates, three machines.** Each person clones the repo and opens Claude Code at the repo root.

**Option B: one machine, three sessions.** Use git worktrees so the agents don't share a working tree:

```bash
git worktree add ../adilet-ml -b ml/dev
```

```bash
git worktree add ../adilet-be -b be/dev
```

```bash
git worktree add ../adilet-fe -b fe/dev
```

Open one Claude Code session in each folder. Merge to `main` through PRs at least at every gate.

---

## 2. Messages to send

Copy these as they are, replacing `<role>` with `ml`, `backend` or `frontend`.

### Kickoff (the first message of the first session)

```
You are the <ROLE> agent of the Adilet Search project.
1. Read CLAUDE.md, docs/PROJECT_PLAN.md and agents/<role>/00_general.md.
   00_general.md is your standing brief for this whole session: follow it at all times.
2. Read the contracts and status files that 00_general.md lists.
3. Then execute agents/<role>/01_<name>.md.
Before writing code, reply with a short plan for this phase and the questions you need a human to answer.
```

### Next phase

```
Phase <NN> is accepted. Run git pull --rebase origin main, re-read docs/status/*.md and
contracts/CHANGELOG.md for changes from the other agents, then execute agents/<role>/<NN+1>_<name>.md.
Start with a short plan.
```

### Resume (new session, or after the context was reset)

```
You are the <ROLE> agent of Adilet Search. Restore context: read CLAUDE.md, agents/<role>/00_general.md,
docs/status/<role>.md and the phase file agents/<role>/<NN>_<name>.md we are in.
Continue from "Next steps" in your status file.
```

### Gate check (at the end of every week)

```
Run the gate check in agents/shared/gate_check.md for gate G<N>.
```

### Relay a request from another agent

```
The <OTHER> agent asks (see docs/status/<other>.md, "Requests to other agents"): <paste the request>.
Handle it if it is in your area and compatible with the contracts; otherwise explain why not.
Update your status file when done.
```

### Contract change request (when an agent needs another agent's interface to change)

```
<OWNER ROLE> agent: <REQUESTING ROLE> needs this change to <contract file>: <what and why>.
Assess it. If you accept, follow the contract-change process in CLAUDE.md (edit, CHANGELOG, status).
If it is breaking, list exactly what the other agents must change.
```

### Bug report to another agent

```
Bug found by <ROLE> in your area: <endpoint/file>, steps: <…>, expected: <…, contract reference>,
actual: <…>. Fix it with a test that reproduces it, then update your status file.
```

---

## 3. Schedule (6 weeks; see PROJECT_PLAN §10)

| Week | ML | Backend | Frontend | Gate |
|---|---|---|---|---|
| 1 | `01_corpus` | `01_skeleton` | `01_scaffold` | **G0** |
| 2 | `02_ml_service_v0` | `02_indexer_search` | `02_search` | **G1, walking skeleton** |
| 3 | `03_eval_baseline_A2` | `03_answer_feedback_logging` | `03_answer_article` | **G2** |
| 4 | `04_training_finetuning_A3` | `04_admin_monitoring_resilience` | `04_admin` | **G3** |
| 5 | `05_embeddings_to_finetuning_A4`, then `06_final_model` | `05_testing_ci` | `05_integration_compare_polish` | **G4** |
| 6 | `07_eval_docs_slides` | `06_deployment`, then `07_docs_presentation` | `06_testing_build`, then `07_demo_docs` | **G5** |
| end | — | — | — | `shared/final_assembly.md` (once, by any one agent) |

### Cross-agent dependencies

| Phase | Needs | Workaround while waiting |
|---|---|---|
| BE-02 search | ML-01 sample data, ML-02 service v0 | the fake ML service; index the sample with fake vectors |
| FE-02 onward | `contracts/openapi.json` from BE-01 | temporary types from `api.md` + MSW mocks |
| FE-05 live integration | BE-03 and BE-04 running | keep working on mocks |
| BE-06 deploy (final models) | ML-06 manifest v1.0.0 | deploy v0, then reindex |
| ML-07 API evaluation | BE-06 deployed URL | run against the local compose stack |

---

## 4. What the humans do

Agents cannot do these things. Plan time for them.

| When | Task | Who |
|---|---|---|
| before week 1 | move the repo out of OneDrive, set up GitHub, HF org, tokens; ask the customer for a DB export and a test VM | team lead |
| weeks 1–6 | review and merge PRs; relay requests between agents; run the gate checks | each owner |
| weeks 2–3 | edit gold queries; label relevance (~3–4 h per person); double-label 20 queries for agreement | all three |
| weeks 3–5 | run training notebooks on Colab/Kaggle; commit `ml/experiments/<run>/` folders | ML owner |
| week 5 | rent a VPS and domain (or get the customer's VM); review the Kazakh UI strings | Backend owner, a Kazakh speaker |
| week 6 | rehearse the demo; record the backup video; build the final slides | all three |

### Reviewing an agent's phase

Before sending the next phase:

1. Run the "how to verify" commands from the agent's last reply.
2. Check that the status file is updated.
3. Check that the acceptance criteria in the phase file are met.
4. Merge the PR.

If something is wrong, tell the agent what failed; don't move on.

### Keeping agents on track

- If an agent starts editing another agent's directory, stop it and point to CLAUDE.md "Who owns what".
- If an agent invents API fields, point it to `contracts/` and the change process.
- If a session gets long and slow, start a fresh one with the **Resume** message. The status file carries the context.
