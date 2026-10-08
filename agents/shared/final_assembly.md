# Final assembly: the deck and the documentation index

Run this **once**, after ML-07, BE-07 and FE-07 are merged. Any one agent can run it (or a human with Claude). It edits only `docs/presentation/final_deck.md`, `docs/presentation/final_deck.pptx|pdf` and `docs/tech/README.md`.

## Inputs
- `docs/presentation/sections/{ml,backend,frontend}.md`
- `docs/report/final_eval.md`, `docs/report/load_test.md`, `ml/reports/results.csv`
- `docs/presentation/img/` (screenshots, charts, architecture diagram)
- `docs/PROJECT_PLAN.md` §13 (slide structure)

## Steps
1. **Assemble** `docs/presentation/final_deck.md` (Marp) with exactly this structure. Use a title slide with the project name, team and customer, then at most 10 content slides:
   1. Problem
   2. Dataset
   3. Model
   4. Experimental results
   5. Final model
   6. System architecture
   7. Deployment
   8. Demonstration
   9. Performance
   10. Limitations and future work
2. **One message per slide.** Each slide gets a headline that states its takeaway (e.g. "Fine-tuning lifts nDCG@10 from 0.41 to 0.58"), at most ~40 words of body text, and one figure or table. Details go in the speaker notes (`<!-- … -->`).
3. **Check every number** against its source file and cite the source in the speaker notes. List any number you could not trace instead of keeping it.
4. **Make it consistent.** The same metric names everywhere (nDCG@10, Recall@10, MRR@10, p95), the same model names as in the manifest, the same pipeline version.
5. **Export:**
   ```bash
   npx @marp-team/marp-cli docs/presentation/final_deck.md --pptx -o docs/presentation/final_deck.pptx
   ```
   ```bash
   npx @marp-team/marp-cli docs/presentation/final_deck.md --pdf -o docs/presentation/final_deck.pdf
   ```
6. **Write** `docs/tech/README.md`: an index of all technical documentation, one line per file, plus links to the deployed URL, the HF repos and the notebooks.
7. **Report:**
   - the slide list with headlines;
   - any untraceable numbers;
   - open gaps in the docs;
   - a 60-second elevator pitch the presenter can memorise.
