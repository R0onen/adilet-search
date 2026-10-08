# ML-01: Environment, corpus and sample release (week 1; full corpus by G2)

**Goal:** a clean, schema-valid corpus of the Tier-1 acts in RU and KK. A small sample is committed **within ~2 days**, so Backend and Frontend can work with real text.

**Ask the human first:**
- Did Tehsnab Group provide a DB export? If yes, write an importer for it instead of the scraper, with the same output schema. If the answer is pending, start with the scraper.
- What is the HF namespace, and is `HF_TOKEN` available in `.env`?

## Tasks

1. **Scaffold `ml/`.**
   - A uv project (Python 3.12) with the package `adilet_ml`, ruff, pytest, a `ml/README.md`, and `ml/requirements-colab.txt` exported from the lockfile.
   - Write `data/README.md` describing the data folder layout from `contracts/data_schema.md` §1.

2. **Target list: `ml/configs/corpus.yaml`.** One entry per act with `doc_id`, `short_title_ru`, `short_title_kk`, `doc_type`, `tier`, `languages`.
   - **Tier 1:** Labor Code; Code on Administrative Offences; Civil Code (General Part, Special Part); Tax Code; Environmental Code; Entrepreneurial Code; Criminal Code.
   - Look up and **verify every `doc_id` on adilet.zan.kz.** For example, the Labor Code is believed to be `K1500000414`, but verify it.
   - The Tax Code was replaced recently, so make sure you take the edition **currently in force**.

3. **Ingestion: `adilet_ml.ingest`.**
   - Fetch `https://adilet.zan.kz/rus/docs/{doc_id}` and `…/kaz/docs/{doc_id}` (or read the customer export).
   - Cache raw HTML in `data/raw/adilet/{lang}/{doc_id}.html` and record the fetch time.
   - Use a polite client: check robots.txt, at most 1 request/s, retries with exponential backoff, a descriptive User-Agent, and skip anything already cached.

4. **Parsing.**
   - Extract document metadata: title, type, number, adoption date, revision date, status.
   - Extract the structure:
     - RU markers: «Раздел», «Глава», «Статья N.».
     - KK markers: «бөлім», «тарау», «N-бап.» (in Kazakh the number comes **before** the word).
   - Move amendment footnotes («Сноска.» / «Ескерту.») into `amendment_notes`. Keep them out of `text`.
   - Detect excluded articles («Исключена…» / «алып тасталды») and set `unit_status = excluded`.
   - Capture adilet's article anchors for `source_url` if they are present and stable.
   - Acts without articles: the unit is the top-level point (`pt{n}`).

5. **Chunking.**
   - One chunk per article. Articles longer than `max_chunk_tokens` (default 400, counted with the tokenizer `intfloat/multilingual-e5-base`) are split at point/paragraph boundaries with a 1-paragraph overlap.
   - Build `text_for_embedding` with the header format from `data_schema.md` §5.
   - Set `chunking_version = "ch1"`.

6. **RU↔KK linking.** Link parallel articles by `doc_id` + `unit_key` into `parallel_article_id`, and report the match rate per act.

7. **Validation and QA.**
   - A pydantic or pandera schema that mirrors `contracts/data_schema.md` exactly; validation runs as part of the release script.
   - QA report `ml/reports/data_quality.md` covering:
     - counts per act and language;
     - gaps in article numbering (explain each one: excluded, renumbered, or a parse error);
     - length distributions in chars and tokens;
     - empty or duplicate texts;
     - % of excluded articles;
     - % with a parallel version;
     - 5 examples of tricky parses.
   - 3–4 charts in `ml/reports/figures/`. They will be reused in the A2 slides.

8. **Release, in two steps.**
   - **Sample (fast):** Labor Code RU + KK only, written to `data/sample/` (documents, articles, chunks Parquet files) plus `sample_articles.json` (30 varied articles, including a long split one, an excluded one and one with amendment notes). Commit it, then write "sample ready" with row counts in your status file.
   - **Full Tier-1:**
     - write the files to `data/processed/` and write `data/MANIFEST.json`;
     - upload to the HF dataset repo `<ns>/adilet-corpus`, tagged with the `corpus_version`;
     - add `ml/scripts/download_data.py --corpus-version X` for everyone else.

9. **Tests.**
   - Parser unit tests on saved HTML fixtures in `ml/tests/fixtures/` (at least one RU and one KK page) covering:
     - an excluded article;
     - a footnote;
     - a hyphenated number such as 113-1;
     - a chapter boundary.
   - A schema test on `data/sample/`.
   - A chunking test: every chunk ≤ max tokens, and the chunks of an article cover its text.

## Acceptance criteria

- [ ] `uv run pytest` passes in `ml/`. `data/sample/` validates against the schema.
- [ ] The QA report explains every numbering gap in the Tier-1 codes and reports the parallel match rate.
- [ ] The sample is committed and announced in the status file (paths, `corpus_version`, row counts, columns that are often null).
- [ ] The full corpus is on the HF Hub and downloadable by script (may finish in week 2; it must be done by G2).

## Handoff

- **Backend:** the paths, `corpus_version`, row counts, and any field that is often null.
- **Frontend:** `data/sample/sample_articles.json`, plus notes on fields the UI will want: status, amendment notes, parallel id.
