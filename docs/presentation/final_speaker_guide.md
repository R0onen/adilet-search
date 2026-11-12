# Final defence: speaking guide

The deck has 10 slides. Aim for 6–8 minutes including a short live demonstration, then questions.
Use the notes in the PowerPoint for sources and measurement limits. Avoid the superseded A3/A4
reports when quoting numbers. The current experiment evidence is `ml/experiments/research-final/results.json` and
`docs/report/RESEARCH_FINDINGS.md`; the earlier lexical CSV is a separate baseline.

## Suggested split

| Presenter | Slides | Purpose |
|---|---|---|
| First teammate | 1–3 | Explain the problem, dataset and retrieval pipeline |
| Second teammate | 4–6 | Explain measured results, model identity and architecture |
| Third teammate | 7–10 | Run the prototype, explain performance and limitations |

Agree names within the group; this split does not claim who implemented each component.

## Opening (about 45 seconds)

“Our project is Adilet Search, a search assistant for Kazakhstan legislation. People often ask
questions in everyday language, while statutes use formal terms. We combine keyword search with
multilingual semantic retrieval and show the exact article behind each result. The interface
supports Russian and Kazakh. An optional generation step can write an answer from retrieved
sources, but the source text remains available so the user can check it.”

## Results (about 45 seconds)

“Following the midterm feedback, we tested whether recent embeddings improve legal article retrieval. We compared E5 with BGE-M3, Qwen3 and EmbeddingGemma 2 on the same full body-only corpus and frozen validation/test queries. We also removed the reranker to measure its contribution. We selected the candidate using validation, then reported test scores separately for Russian and Kazakh, with paired uncertainty intervals. These are title-derived proxy questions: our findings do not establish general legal accuracy. The LLM rewriting experiment is a separate small pilot, and did not establish a benefit.”

Use the exact values on slide 4 and in `RESEARCH_FINDINGS.md`. Explain a ranking failure from
the report rather than claiming that a single aggregate score proves legal understanding.

## Live demonstration (about 90 seconds)

1. Open http://127.0.0.1:18080 and confirm it shows live mode.
2. Ask: “Какова нормальная продолжительность рабочего времени?”
3. Open the first result. Check that it is Labor Code article 68 and inspect the exact text.
4. Switch the article to Kazakh. Explain that the stored parallel article is shown.
5. Close the drawer and request an answer. The current local stack uses the configured external LLM; a fresh checkout defaults
   to extractive fallback. State which mode is active. Open a source button to check the underlying article.
6. Open the comparison page if time permits. Explain that one example cannot establish which
   model is generally better.
7. Open Grafana and show the service-up and request panels after actual traffic.

If the first result is wrong, say so and inspect it. Do not switch to scripted mock mode and
describe it as a live model. If the service is unavailable, use the saved live screenshot and
explain what was verified and when.

## Questions to prepare

**Did you train the models?** The currently served E5 and cross-encoder models are pretrained.
No project-specific fine-tuned checkpoint is evidenced by the current run folder. We must keep
that distinction clear. An instructor may require our own fine-tuning for the earlier assignments;
that remains a separate required experiment, not something a pretrained checkpoint proves.

**Why hybrid retrieval?** BM25 retains exact lexical matches; E5 adds semantic similarity. RRF
combines their rankings and a cross-encoder scores candidate query/article pairs.

**How do you know an answer is correct?** We validate that numbered citations reference supplied
sources and let users inspect those sources. This does not prove that each claim follows from
the text. Human faithfulness evaluation remains necessary.

**Are the laws current?** This corpus is a dated snapshot. We do not claim that all later
amendments are included or that a generated answer establishes current legal validity.

**Is the two-second target achieved?** Quote only the latest measured result in
`docs/report/final_load.json`, including concurrency, errors and degraded responses. The target
is not achieved merely because one request is fast. The first 10-user test failed.

**Is it publicly deployed?** The verified deployment is local Docker Compose. A local address
is not reachable by an external grader. Public HTTPS hosting is still pending.

**What is the main next step?** A human-labelled RU/KK test set, comparable model experiments,
training artifacts where required, and a deployment/load result that meets the chosen scope.
