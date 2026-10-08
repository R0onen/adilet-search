# Data contract (v1)

- **Owner:** ML.
- **Consumers:** Backend (indexer, Postgres), Frontend (mock fixtures), ML (everything).

All Parquet files are written with pyarrow. Text is UTF-8, normalised to NFC, with whitespace collapsed. Statute wording is otherwise unchanged.

---

## 1. Files

| Path | Content | In git? |
|---|---|---|
| `data/raw/adilet/{ru,kk}/{doc_id}.html` | cached source pages | no |
| `data/processed/documents.parquet` | one row per (doc_id, lang) | no (HF dataset `<ns>/adilet-corpus`) |
| `data/processed/articles.parquet` | one row per article/unit, full text | no (HF) |
| `data/processed/chunks.parquet` | one row per chunk, metadata denormalised | no (HF) |
| `data/MANIFEST.json` | `corpus_version`, sha256 per file, row counts, `scraped_at` | yes |
| `data/sample/{documents,articles,chunks}.parquet` | Labor Code RU + KK subset, same schema | yes |
| `data/sample/sample_articles.json` | 30 articles from `articles.parquet` as JSON (for frontend mocks) | yes |
| `data/eval/queries.jsonl`, `qrels.jsonl`, `splits.json` | evaluation data | yes |
| `data/eval/labeling/` | labelling batches (CSV) + `GUIDE.md` | yes |
| `data/sft/{train,val}.jsonl` | generator SFT data | no (HF dataset `<ns>/adilet-sft`) |
| `data/index/embeddings_{pipeline_version}.parquet` | precomputed passage vectors: `chunk_id`, `dense` (list<float32>), `sparse_indices`, `sparse_values` | no (HF) |

---

## 2. Identifiers

- **`doc_id`:** the adilet document code, the same for RU and KK, e.g. `K1500000414`.
- **`unit_key`:** identifies the unit inside a document.

  | Unit | Format | Example |
  |---|---|---|
  | article | `a{number}` | `a113`, `a113-1` |
  | top-level point | `pt{n}` | `pt5` |
  | chapter (acts without articles or points) | `ch{n}` | `ch2` |
  | preamble | `pre` | `pre` |
  | annex | `ann{n}` | `ann1` |

  Allowed characters: `[a-z0-9-]`.
- **`article_id`** = `{doc_id}:{lang}:{unit_key}`, e.g. `K1500000414:ru:a113`.
- **`chunk_id`** = `{article_id}:c{chunk_index}`, e.g. `K1500000414:ru:a113:c0`.
- **`group_key`** = `{doc_id}:{unit_key}`. It is language-independent and is used for splits.
- **Qdrant point id** = `uuid5(NAMESPACE_URL, chunk_id)`.

---

## 3. `documents.parquet`

| column | type | null? | notes |
|---|---|---|---|
| `doc_id` | string | no | |
| `lang` | string | no | `ru` / `kk` |
| `title` | string | no | full official title |
| `short_title` | string | no | e.g. «Трудовой кодекс РК» (from `ml/configs/corpus.yaml`) |
| `doc_type` | string | no | `code`, `law`, `decree`, `resolution`, `order`, `other` |
| `number` | string | yes | e.g. `414-V` |
| `adopted_date` | date | yes | |
| `revision_date` | date | yes | date of the latest amendment in the text |
| `status` | string | no | `in_force`, `repealed`, `not_yet_in_force` |
| `source_url` | string | no | |
| `article_count` | int32 | no | |
| `scraped_at` | timestamp | no | UTC |
| `corpus_version` | string | no | `YYYY.MM.DD[-n]` |

## 4. `articles.parquet`

| column | type | null? | notes |
|---|---|---|---|
| `article_id` | string | no | primary key |
| `doc_id`, `lang` | string | no | |
| `unit_type` | string | no | `article`, `paragraph`, `chapter`, `preamble`, `annex` |
| `unit_key` | string | no | |
| `unit_number` | string | yes | `113`, `113-1` |
| `unit_title` | string | yes | |
| `unit_order` | int32 | no | 0-based position in the document |
| `unit_status` | string | no | `in_force` or `excluded` (from «Исключена…» / «алып тасталды») |
| `section_title`, `chapter_title` | string | yes | |
| `text` | string | no | full verbatim text, line breaks preserved, footnotes removed |
| `amendment_notes` | list<string> | no | the «Сноска.» / «Ескерту.» notes (empty list if none) |
| `has_amendments` | bool | no | `len(amendment_notes) > 0` |
| `source_url` | string | no | with an anchor if available |
| `parallel_article_id` | string | yes | the same unit in the other language |
| `content_hash` | string | no | sha256 of `text` |

## 5. `chunks.parquet`

Every column of `articles.parquet` **except** `text` and `amendment_notes`, plus:

| column | type | null? | notes |
|---|---|---|---|
| `chunk_id` | string | no | primary key |
| `chunk_index` | int16 | no | 0-based |
| `chunk_count` | int16 | no | |
| `text` | string | no | the chunk text (verbatim slice of the article text; neighbouring chunks overlap by one paragraph) |
| `text_for_embedding` | string | no | header line + `\n` + chunk text. Header: `«{short_title}. Статья {N}. {title}»` (RU) or `«{short_title}. {N}-бап. {title}»` (KK) |
| `doc_title`, `doc_short_title`, `doc_type`, `doc_status`, `adopted_date`, `revision_date` | as in documents | | denormalised for the Qdrant payload |
| `char_len`, `token_len` | int32 | no | `token_len` uses the tokenizer named in the manifest `chunking.tokenizer` |
| `chunking_version` | string | no | e.g. `ch1` |
| `corpus_version` | string | no | |

---

## 6. Evaluation files

**`queries.jsonl`**, one query per line:
```json
{"query_id": "g0001", "text": "Какая ответственность работодателя за задержку зарплаты?", "lang": "ru", "source": "gold", "persona": "accountant", "query_type": "plain", "answerable": true}
```

| field | values |
|---|---|
| `source` | `gold` / `synthetic` |
| `persona` | `lawyer` / `accountant` / `entrepreneur` / `citizen` / `null` |
| `query_type` | `plain` / `terminology` / `article_ref` |
| `query_id` prefix | `g` for gold, `s` for synthetic |

**`qrels.jsonl`**, one judgement per line:
```json
{"query_id": "g0001", "article_id": "K1500000414:ru:a113", "relevance": 2}
```
- `relevance`: `2` = directly answers, `1` = related or partially answers, `0` = judged not relevant (keep these; they record what was in the pool).
- Qrels are in the query's language.

**`splits.json`**:
```json
{
  "version": "splits_v1",
  "seed": 42,
  "group_key": "doc_id:unit_key",
  "synthetic": {"train": ["<group_key>", "…"], "val": ["…"], "test": ["…"]},
  "gold": {"val": ["g0003", "…"], "test": ["g0001", "…"]},
  "sha256": {"queries.jsonl": "…", "qrels.jsonl": "…"}
}
```
- A synthetic query belongs to the split of the group of its source article.
- Gold queries are never in train.

---

## 7. SFT data (`data/sft/*.jsonl`)

```json
{
  "messages": [
    {"role": "system", "content": "<system part of prompts/answer_v1.md>"},
    {"role": "user", "content": "<user part filled with the question and numbered sources>"},
    {"role": "assistant", "content": "Работодатель обязан … [1]. За задержку … [2]."}
  ],
  "meta": {"query_id": "s01234", "lang": "ru", "answerable": true, "source_article_ids": ["…"], "origin": "teacher", "human_reviewed": false}
}
```

---

## 8. Index layout (implemented by Backend; changes need both owners)

**Qdrant**
- Collection `legal_chunks__{pipeline_version}`, reached through the alias `legal_chunks`.
- Named dense vector `dense`: size `embedder.dim`, distance Cosine, HNSW `m=16`, `ef_construct=128`.
- Named sparse vector `sparse`: `modifier: idf`.
- **Payload:** `chunk_id`, `article_id`, `doc_id`, `lang`, `doc_type`, `doc_status`, `unit_status`, `adopted_date` (stored as an integer `YYYYMMDD`), `unit_number`, `unit_title`, `doc_short_title`, `text`, `text_for_embedding`, `source_url`.
- **Payload indexes:** keyword indexes on `lang`, `doc_id`, `doc_type`, `doc_status`, `unit_status`; an integer index on `adopted_date`.

**Postgres**
- `documents` and `articles` are loaded from the Parquet files. `articles` has a generated `tsvector` column (`russian` config for `ru`, `simple` for `kk`) with a GIN index, used for the full-text fallback.
- `index_state` records, per collection: `pipeline_version`, `index_compat_id`, `corpus_version`, point count and creation time.

---

## 9. Versioning

- **`corpus_version`** changes whenever the corpus content changes (new acts, a re-scrape). Old versions stay downloadable from the HF dataset by revision.
- **A schema change** (renamed or removed column, changed meaning) bumps this contract's version and needs a CHANGELOG entry. Adding a nullable column is additive.
