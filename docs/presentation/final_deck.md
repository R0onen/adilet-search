---
marp: true
paginate: true
---

# Find the law behind the question

People ask in everyday words; the law answers in its own.

Adilet Search: a question in Russian or Kazakh → the articles that answer it, and a short answer that cites them.

<!-- Built as the AI module of the Legal Service platform. Keyword search finds an article only when the question uses its words: 'задерживают зарплату' does not occur in the Labor Code, 'сроки выплаты заработной платы' does. The system is a search aid, not legal advice. -->

---

# Official texts and 803 test questions

Corpus: AdiletCodex v1.0 (adilet.zan.kz), snapshot of 17 September 2026

Deployed: 40 acts · 20,490 articles in Russian and Kazakh · 41,074 chunks

Experiments: 8 codes · 9,259 articles

Questions: 803 written by an LLM for 400 articles, split by article 70 / 15 / 15

A person checked 60 of the 195 test questions: 53 correct

<!-- Sources: ml/MODEL_CARD.md, data/eval/synthetic/meta.json, data/eval/labeling/synthetic_review_summary.json. Texts are stored verbatim. Each question has one labelled article (the one it was written for); no article is in two splits. The review found 3 wrong and 4 too vague questions out of 60. There is no gold set written by lawyers. -->

---

# Retrieve, rerank, then answer from the sources

1. Everyday words → legal terms (dictionary)

2. Dense search (multilingual E5) + keyword search (BM25)

3. Reciprocal-rank fusion of the two lists

4. Cross-encoder reranker, fine-tuned on our questions

5. LLM writes an answer from the top articles and cites them [1], [2]

<!-- Embedder: intfloat/multilingual-e5-base, pretrained. Reranker: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, fine-tuned by us (Assignment 4). The backend removes citations that do not point to a provided source. If the models or the vector index are down, search falls back to PostgreSQL full-text search. -->

---

# From keywords to a fine-tuned transformer

| Model | Kind | nDCG@10 | ROC-AUC |
|---|---|---|---|
| BM25, tuned | classical | 0.697 | – |
| TF-IDF features + Logistic Regression | classical | 0.727 | 0.923 |
| E5 embedding + lexical features + boosting | embeddings + ML | 0.753 | 0.953 |
| Qwen2.5-0.5B + LoRA | LoRA | 0.805 | 0.951 |
| Cross-encoder, pretrained | transfer | 0.867 | 0.959 |
| Cross-encoder, fine-tuned (served) | fine-tuning | 0.880 | 0.973 |

195 test questions · reranking 20 candidates · ceiling 0.923

<!-- Task: rerank 20 BM25 candidates for 195 test questions; the ceiling is 0.923. Sources: docs/report/A3_report.md, docs/report/A4_report.md, executed notebooks in ml/notebooks/. The pretrained cross-encoder is the largest step (+0.114 over the best embedding model, p < 0.001). Fine-tuning on the 4,264 pairs from written questions adds +0.013 (95% interval +0.003 to +0.025, p = 0.016) and improves the classifier (F1 0.598 → 0.652). LoRA on a small general LLM is below the cross-encoder and 7 times slower to train. A separate comparison of embedding models (BGE-M3, Qwen3, EmbeddingGemma) on title queries is in docs/report/RESEARCH_FINDINGS.md. -->

---

# Pipeline 1.0.0, measured through the live API

| Index | Reranker | Right article first | nDCG@10 |
|---|---|---|---|
| 8 codes | pretrained | 83.1% | 0.885 |
| 8 codes | fine-tuned | 85.1% | 0.895 |
| 40 acts (deployed) | fine-tuned | 82.6% | 0.871 |

Fine-tuned against pretrained: +0.013 nDCG@10 offline, p = 0.016
Human-approved questions: right article first for 83.0%
55 everyday questions on the added acts: first 58%, top 10 87% (keyword search: 26%, 64%)

<!-- Source: ml/experiments/final-selection/. Hybrid mode, 5 reranked candidates, 195 test questions. On the 53 human-approved questions the right article is first for 83.0% on both indexes. Adding 32 acts costs 2.5 points on questions written for the 8 codes, because other acts regulate the same subjects. The version is fixed in ml/models/model_manifest.json with pinned model revisions; the reranker is published on the Hugging Face Hub. Inputs and outputs: contracts/api.md. -->

---

# One API between the UI and the models

React UI: search, answer, article viewer, admin

FastAPI: search and answer API, query log

ML service: E5, fine-tuned reranker, LLM client

PostgreSQL: articles, logs, full-text fallback

Qdrant: dense + sparse index

Caddy (HTTPS) in front · Prometheus → Grafana behind

<!-- Docker Compose: frontend (nginx), backend (FastAPI), ML service, PostgreSQL, Qdrant, Caddy for HTTPS, Prometheus and Grafana. The interfaces are fixed in contracts/. The admin panel shows usage, the query log, health and reindexing. -->

---

# One command on a small server

docker compose -f docker-compose.prod.yml up -d

Only the proxy's port is open; HTTPS from Caddy on a server or from an ngrok tunnel

The index is built once on a GPU and copied to the server

Live demo: https://bacterium-margarita-coveted.ngrok-free.dev

<!-- The live demo runs this stack on a team machine behind an ngrok tunnel; the first visit shows ngrok's warning page (click Visit Site). Guide: docs/tech/deployment.md; sizing: docs/tech/infrastructure_sizing.md. CI runs unit, contract and integration tests, a dependency audit and a full-stack smoke test on every pull request. -->

---

# Ask, read the article, check the answer

«Работодатель задерживает зарплату — что делать?»

«Можно ли вернуть товар в магазин без чека?»

«Жұмыс уақытының қалыпты ұзақтығы қандай?»

Open a cited article · switch Russian ↔ Kazakh · admin panel

<!-- Script: docs/presentation/demo_script.md. Show the ranked articles first, then the generated answer and its citations, then the full article text. Show a question the corpus does not answer: the answer says so and reports what the articles do say. -->

---

# Fast enough for 10 users at once

Load test: 10 users at once, cache off, 40-act index, CPU only

981 searches · no errors · 1 answered without reranking (0.1%)

p50 0.65 s · p95 1.2 s · target p95 ≤ 2 s

One search alone: about 0.35 s

Answers: 40 of 40 generated, each cites the right article when retrieved; first words after 0.7 s

<!-- Source: docs/report/load_test.md (10 simulated users, cache off, every request through embedding, retrieval and reranking, 5 minutes). Tests: backend unit, contract and integration tests, ML tests, frontend tests; counts in docs/report/final_readiness.md. Answers: docs/report/final_eval.md (30 human-approved questions and 10 Kazakh ones, hosted LLM). -->

---

# What the numbers do not show

Test questions are LLM-written; 60 were checked by a person, none by a lawyer

Kazakh is weaker than Russian (reranker nDCG@10 0.83 against 0.91)

Everyday questions on the added acts: right article first for 58%, not 83%

15 of 35 reranker errors: the article never reaches the reranker

The corpus is a snapshot; later amendments are not in it

Next: Kazakh training questions, a larger dictionary, a lawyer-written gold set

<!-- Sources: docs/report/A4_report.md (error analysis), ml/MODEL_CARD.md (limits). The generator can misread a source; the backend checks that citations point to provided sources, not that the source supports the claim. -->
