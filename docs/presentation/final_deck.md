---
marp: true
paginate: true
---

# Find the law behind the question

Adilet Search · Kazakhstan legislation

Russian and Kazakh questions → articles with sources

<!-- Keyword search misses everyday wording. Our prototype combines lexical and semantic retrieval, then can generate a source-cited answer. Team: Daniil Talyzin, Yernur Kazhyakpar, Kuanysh Murat. This is a course prototype for the Legal Service use case; production integration is not claimed. Source: README.md; docs/PROJECT_PLAN.md §1. -->

---

# Official text, a bounded snapshot

8 Tier-1 code documents · RU + KK

9,259 article-language records · 16,264 chunks

Snapshot: 17 September 2026

<!-- AdiletCodex v1.0, CC BY 4.0; see ml/MODEL_CARD.md and ml/scripts/download_data.py. A fresh rebuild reproduced 16 document-language rows, 9,259 articles and 16,264 chunks. These counts include both languages; do not say 9,259 distinct bilingual articles. Text is preserved; amendment notes are separate. The snapshot does not establish current legal validity. -->

---

# Test models, fusion and LLM rewriting

Does a newer embedder improve retrieval?

Does hybrid reranking help RU and KK?

Does an LLM rewrite justify its extra cost?

<!-- Research sources: docs/report/RESEARCH_PROTOCOL.md; ml/experiments/research-*/results.json. Title-derived proxy labels, not human gold. -->

---

# Newer models must earn their place

| Method | Val nDCG@10 | Test nDCG@10 | RU | KK |

|---|---:|---:|---:|---:|

| e5 | 0.706 | 0.703 | 0.802 | 0.605 |

| current_hybrid_reranker | 0.856 | 0.846 | 0.855 | 0.836 |

| hybrid_no_reranker | 0.778 | 0.770 | 0.816 | 0.724 |

| qwen3 | 0.539 | 0.548 | 0.667 | 0.430 |

| bge_m3 | 0.830 | 0.822 | 0.833 | 0.812 |

| embeddinggemma2 | 0.710 | 0.716 | 0.802 | 0.630 |

<!-- Research sources: docs/report/RESEARCH_PROTOCOL.md; ml/experiments/research-*/results.json. Title-derived proxy labels, not human gold. Full corpus: 16,264 body-only chunks. Validation: 1,311; test: 1,318. Same 512-token budget, language filtering and article collapse. The hybrid reproduction uses local BM25, RRF k=60 equal weights and top-20 reranking; Qdrant IDF differs. Scores compare practical pretrained configurations; no project-specific fine-tuning or isolated architecture effect is claimed. -->

---

# Hybrid remains the measured candidate

Hybrid − E5 test nDCG@10: +0.142

Paired 95% interval: [+0.123, +0.162]

LLM rewrite: small pilot; no benefit established

<!-- Research sources: docs/report/RESEARCH_PROTOCOL.md; ml/experiments/research-*/results.json. Title-derived proxy labels, not human gold. Validation selects the candidate; test estimates performance. Intervals group parallel RU/KK article families. This is a fixed-cohort proxy study; no multiple-comparison correction or human-gold claim. EmbeddingGemma 2 uses supported BF16, other embedding models FP16. The served pipeline remains version 0.2.0: multilingual-e5-base plus cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, with pinned checkpoints. See RESEARCH_FINDINGS.md and ml/models/model_manifest.json. -->

---

# One API joins retrieval and the UI

React UI → FastAPI API

PostgreSQL + Qdrant + ML service

Prometheus → Grafana

<!-- Search: embed query, dense/sparse retrieval, RRF fusion, article collapse, cross-encoder rerank. Answer: retrieve sources, stream generation via SSE, validate citation references. Frontend source drawer supports RU/KK. Architecture sources: docker-compose.yml; docker-compose.final.yml; backend/app/state.py; frontend/src/App.tsx. Monitoring additions require runtime verification; planned components must not be described as deployed until that succeeds. -->

---

# The prototype runs in Docker

Live UI + API + real model inference

Prometheus targets up · Grafana healthy

Local access verified · public HTTPS pending

<!-- Use docs/tech/final_project.md. Local build and public hosting are separate claims. An accessible local demonstration is the immediate target; the project plan also asks for public HTTPS. There is no verified public URL in the repo. Do not expose admin stubs or database ports to the public internet. No VPS purchase or account action is performed by this script. Verified in this session: UI http://127.0.0.1:18080, API proxy, source drawer and RU/KK switch. Source: docs/report/final_browser.json. -->

---

# Follow the answer back to the article

Ask about working hours or annual leave

Inspect ranked articles and exact source text

Switch RU ↔ KK; compare keyword and hybrid

<!-- Rehearse using the actual indexed corpus. Start with 'Какова нормальная продолжительность рабочего времени?' and 'Сколько дней ежегодного оплачиваемого отпуска?'. Confirm the retrieved sources before showing generation. Current local generation uses externally pretrained openai/gpt-oss-120b; a fresh checkout defaults to extractive fallback. Try an unsupported question and show the limitation. Prepare a backup recording only after a successful live rehearsal. Sources: docs/presentation/demo_script.md; frontend/src/App.tsx. -->

---

# Load testing exposes the CPU limit

100 requests · 10 concurrent users

HTTP errors: 0 · degraded: 60

Complete-response p95: 2,531 ms · target not met

<!-- The latency target is from docs/PROJECT_PLAN.md §8 and is not a measured result. Current checks: 49 ML, 258 backend unit/contract, 34 storage/integration and 6 real-ML checks; 12 frontend unit tests and 4 browser scenarios. Updated totals and runtime results belong in docs/report/final_readiness.md. Measure non-degraded coverage, error rate, model IDs and hardware alongside latency. A fast degraded response is not evidence that full semantic search met the target. Latest source: docs/report/final_load.json. This is a repeated-question sample-corpus load test. No full-corpus generalization is claimed. -->

---

# The next step is stronger evidence

Independent human-labelled RU/KK questions

Long-context and prompt-sensitivity experiments

Scale LLM pilot; measure faithfulness and API load

<!-- The full frozen proxy experiment now compares recent pretrained models. No project-specific fine-tuning is claimed. Do not generalize title-query metrics to legal advice or generated-answer correctness. Public hosting and CPU load acceptance remain outstanding. Research sources: docs/report/RESEARCH_PROTOCOL.md; ml/experiments/research-*/results.json. Title-derived proxy labels, not human gold. -->
