# Official baseline ingestion and difficult-question diagnostics

## What is running now

The local live app uses the complete article text extracted from two official codes in RU and KK:

| Official source | RU article records | KK article records |
|---|---:|---:|
| [Labor Code](https://old.adilet.zan.kz/rus/docs/K1500000414) | 227 | 227 |
| [Environmental Code](https://old.adilet.zan.kz/rus/docs/K2100000400) | 426 | 426 |
| Total | 653 | 653 |

These are 653 article identifiers represented in two languages: 1,306 article-language records, 2,799 passage chunks and four document-language records. Eighteen article-language records are marked excluded based on the source's removal notes. Default in-force search excludes them. The old three-article corpus and committed bootstrap sample remain available; old Qdrant collections were retained.

This is a downloaded educational snapshot. Revision dates are unknown. Current effective dates and staged amendments have not been resolved; do not describe the snapshot as a verified legal database for a specific date.

## How ingestion works

`frontend/scripts/build_official_baseline.py` is a presentation integration tool using dependencies already installed in the ML container. It does not change ML/backend-owned source files.

1. Read the source site's robots policy; fetch four explicitly listed document pages sequentially, with at least one second between uncached requests. No search-page crawling, archive crawling, or recursive following of links.
2. Cache source HTML with retrieval timestamps and SHA-256 hashes. Reuse cached pages; offline mode makes no network requests.
3. Parse only the statute's `article` container, supporting bold paragraph and heading article markers. Preserve source wording and paragraph separation; keep amendment notes separate from article text. Preserve actual source anchors, section/chapter metadata and RU/KK parallel IDs.
4. Reject missing containers, suspiciously small documents, duplicate article markers and unexplained empty articles. Removed articles retain their source removal notices with excluded status.
5. Split article text into overlapping exact slices of at most 1,400 characters (up to 180-character overlap). Record the local chunking variant as `demo-char1400-v1`; a production manifest update belongs to ML. No statute text is rewritten by an LLM.
6. Write contract-shaped Parquet tables plus article JSON, quality JSON, provenance JSON and raw HTML. The existing backend indexer validates all tables, upserts PostgreSQL and switches the Qdrant alias after indexing.

To add another code, extend `ACTS` with a verified official document ID and metadata. Run a new snapshot, inspect its quality report, and test parsing for that document's markup before indexing. This parser is tested for these two codes, not every possible Adilet act or annex layout.

## Reproduce or refresh

Run these PowerShell commands from the repository root. Dataset output is ignored by Git.

```powershell
docker cp frontend/scripts/build_official_baseline.py adilet-localtest-ml-service-1:/tmp/build_official_baseline.py
docker cp frontend/scripts/test_official_baseline.py adilet-localtest-ml-service-1:/tmp/test_official_baseline.py
docker compose -p adilet-localtest --env-file .env.localtest --profile ml exec -T ml-service python /tmp/test_official_baseline.py

# Restore the saved cache into the container (it may already be there).
docker cp data/processed/official-baseline/. adilet-localtest-ml-service-1:/tmp/official-baseline
docker compose -p adilet-localtest --env-file .env.localtest --profile ml exec -T ml-service python /tmp/build_official_baseline.py --offline
docker cp adilet-localtest-ml-service-1:/tmp/official-baseline/. data/processed/official-baseline
docker compose -p adilet-localtest --env-file .env.localtest --profile ml exec -T backend python -m indexer --data-dir /data/processed/official-baseline
```

To fetch a deliberately new snapshot, use a new `--out-dir` without `--offline`, inspect the resulting quality report, then copy/index that directory. Never overwrite the historical cache silently.

The extraction/indexing run passed backend corpus validation. Four parser regression tests cover inline-link text, fragmented amendment notes, RU/KK heading markup, duplicate/error pages, navigation exclusion and complete coverage of oversized paragraphs.

## What the difficult-question test found

Run from `frontend`:

```powershell
node scripts/evaluate-baseline.mjs
```

Optionally add `--answers` for five sequential live Groq calls. This spends free API quota; the default retrieval-only test does not call the generator. The question set is original diagnostic material with author-inferred required articles, not a human-labelled gold benchmark or a training set.

Observed retrieval results on 2026-10-08: all expected articles appeared in the top five for **8/13 supported cases**, and in the top ten for **9/13**. Two additional unsupported questions were tested for scope handling. These figures measure source retrieval, not answer accuracy.

| Diagnostic question/topic | Expected sources | Observed result |
|---|---|---|
| Normal working week (RU/KK) | Labor 68 | First result |
| Annual paid leave (RU/KK) | Labor 88 | First result |
| Salary timing and weekend payday | Labor 113 | First result |
| Everyday wording about late payment and compensation | Labor 113 | Missing from top ten |
| Overtime limits, pay and consent | Labor 77, 78, 108 | 108 first, 77 tenth, 78 missing from top ten |
| Everyday wording about being kept after a shift | Labor 78, 108 | 78 fifth, 108 missing from top ten |
| Recall from annual leave | Labor 95 | First result |
| Keeping a job while caring for a child | Labor 100 | Second result |
| Access to environmental information and response timing | Environmental 18, 20 | 20 first, 18 eighth |
| Everyday wording about factory pollution data | Environmental 18 | Missing from top ten |
| Public hearings on an impact report | Environmental 73 | First result |

Live generation exposed additional failures:

- The late-payment paraphrase produced a refusal because the correct article was not retrieved. Increasing corpus size alone did not fix understanding of wording.
- The overtime answer incorrectly inferred that consent was unnecessary from the absence of the consent article in its context. Labor article 77 actually states a written-consent rule with exceptions. This is a substantive answer error even though its citation markers were valid.
- The leave-recall answer's main consent rule was correct, but its wording treated protected categories as exceptions to consent instead of categories that cannot be recalled. The answer is not a clean pass.
- One environmental answer returned a generator-unavailable event. Its cause was not established; retrieval still returned sources.
- The VAT question correctly said that the sources lacked tax information, but cited irrelevant sources and was marked `grounded: true`. The backend's flag checks citation references/refusal phrases, not semantic support.

Detailed local evidence: `frontend/test-results/baseline-retrieval.json`, `baseline-answers.json`, `baseline-build.log`, `baseline-index.log`; snapshot evidence is under `data/processed/official-baseline/`.

## What is needed before claiming adaptive answers

The current retriever uses hash vectors and lexical overlap; it is not a semantic embedder. The user chose to keep current dependencies. More sources broaden coverage but do not resolve this limitation.

ML/backend handoff, with no extra package required for the first two items:

1. Make generation refuse unsupported subquestions, use a consistent refusal phrase, never infer permission from a missing rule, and distinguish prohibitions from exceptions. The current serving function constructs its own short prompt instead of loading `ml/prompts/answer_v1.md`.
2. Evaluate Groq-based query decomposition/terminology expansion and multi-query retrieval for paraphrases, with caching, bounded latency and free-tier quota handling. Preserve the original user question for generation; never rewrite source text. This is an additional retrieval stage, not model training.
3. When dependency changes are authorized, replace hash vectors with a pinned multilingual embedder and a suitable reranker, then reindex the full corpus. The current lexical reranker can demote semantically relevant candidates.
4. Select source passages relevant to each subquestion rather than simply the first characters of a long article. Add evidence-support evaluation; citation existence is insufficient.
5. Use a separate human-reviewed RU/KK evaluation set, including missing-source/refusal cases. Report retrieval and answer correctness independently.

The app is suitable for experimenting with the enlarged corpus. It is not yet reliable for arbitrary difficult legal questions. Public hosting, an exhaustive statutory corpus and legal effective-date validation remain separate work.
