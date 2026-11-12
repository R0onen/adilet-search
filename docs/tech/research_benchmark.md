# Run the research comparison

The experiments are separate from the API demo index. They read the full processed corpus,
not the Labor Code sample. No training or API model replacement occurs.

## Reproduce

From the repository root on a machine with Docker Desktop and an NVIDIA GPU:

```powershell
# Prepares the CUDA image, model service and dependencies; first startup downloads weights.
./infra/start-final.ps1 -Gpu
# Ensure data/processed/chunks.parquet and the three data/eval files exist.
./infra/run-research.ps1 -Full -RevisionsFrom ml/experiments/research-final/results.json
# External LLM calls are opt-in and use the ignored server-side environment configuration.
./infra/run-research.ps1 -LlmRewrite -Models e5 -RevisionsFrom ml/experiments/research-final/results.json
uv run --project ml python ml/scripts/summarize_research.py ml/experiments/research-full/results.json --eval data/eval --out docs/report/research-full
```

The full run defaults to E5, Qwen3, BGE-M3 and EmbeddingGemma 2. E5 also produces the
hybrid/reranker and no-reranker ablations. Use `-Models qwen3` to run one candidate.
The rewrite command uses four queries per language per split, with a matched E5 control.
It overwrites `research-pilot` with the explicitly requested methods; retain the supplied
artifacts elsewhere before rerunning if needed.

Encoder runs are sequential to fit an 8 GB GPU. Gemma's text-only processor also needs
Pillow and a torch-compatible torchvision; the GPU image installs the `research` extra.
Gemma uses BF16, others FP16. Unsupported/invalid outputs raise errors rather than silently
substituting another model. Encodings are cached inside the ML container; a container
recreation may remove experiment caches. Model downloads persist in the named model volume.
Expect downloads and corpus encoding to take longer than query ranking.

The completed study combines an initial five-method run and a separately executed Gemma run:

```powershell
uv run --project ml python ml/scripts/merge_research.py ml/experiments/research-full/results.json ml/experiments/research-gemma2/results.json --out ml/experiments/research-final
uv run --project ml python ml/scripts/summarize_research.py ml/experiments/research-final/results.json --eval data/eval --out docs/report/research-final
uv run --project ml python ml/scripts/verify_research.py ml/experiments/research-final/results.json --eval data/eval
```

Merging refuses different corpus/query fingerprints or duplicate method names. Do not merge
the pilot with the full split. After a fresh all-model run, summarize that run directly;
it already contains all candidates and does not need merging.

## Inspect evidence

- [Research protocol](../report/RESEARCH_PROTOCOL.md): hypotheses and controls.
- [Findings](../report/RESEARCH_FINDINGS.md): measured results, limitations and failure cases.
- [Notebook](../../ml/notebooks/Final_Research_Comparison.ipynb): executable result analysis.
- `ml/experiments/research-final/results.json`: hashes, checkpoints, hardware, scores and intervals.
- Matching `*_rankings.json`: predictions for each query, enabling independent recomputation.

No secrets or model weights belong in the result artifacts. LLM rewrites are cached only in
ignored runtime data. A failed request aborts rather than being replaced by an unrecorded query.
The bootstrap groups parallel RU/KK article queries, uses seed 42 and 2,000 resamples.
Pairwise intervals are exploratory and are not adjusted for multiple comparisons.
The verifier recomputes all 180 split/metric values for the six-method full study, checks
matching query cohorts, duplicate articles and language filters, then records post-run
label/split fingerprints. The runner also records these fingerprints prospectively on new runs.
