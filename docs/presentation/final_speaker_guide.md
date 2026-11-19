# Final defence: speaking guide

The deck has 10 slides: `final_deck.pptx` (speaker notes name the source of every number) and `final_deck.pdf`. Aim for 7–8 minutes including a 3-minute live demo (`demo_script.md`), then questions.

## Suggested split

| Presenter | Slides | Purpose |
|---|---|---|
| First | 1–3 | the problem, the data, the pipeline |
| Second | 4–5 | experiments and the final model |
| Third | 6–10 | architecture, deployment, demo, performance, limits |

## What to say

**Slide 1, problem (30 s).** "People ask about the law in everyday words; statutes use their own. Keyword search fails on 'работодатель задерживает зарплату' because the Labor Code says 'сроки выплаты заработной платы'. Adilet Search finds the article and writes a short answer that cites it."

**Slide 2, dataset (40 s).** "The texts are the public AdiletCodex dataset, parsed from adilet.zan.kz: 40 acts, about 20 thousand articles in Russian and Kazakh, stored verbatim. For training and testing an LLM wrote 803 questions for 400 articles, split by article so that no article is in both training and test. We checked 60 test questions by hand: 53 were correct."

**Slide 3, model (40 s).** "Five steps: a small dictionary turns everyday words into legal terms; dense and keyword search each propose articles; their lists are fused; a cross-encoder that we fine-tuned reorders the top; an LLM answers from those articles only."

**Slide 4, experiments (60 s).** "The task is to rerank 20 candidates. Keyword and classical models stop at 0.73 nDCG@10; adding embeddings gives 0.75; a pretrained cross-encoder jumps to 0.87 with no training; fine-tuning it on our questions gives 0.88. LoRA on a small general LLM was worse and seven times slower. The largest step is transfer learning; fine-tuning adds a small but statistically significant gain, p = 0.016."

**Slide 5, final model (40 s).** "Through the live API the fine-tuned reranker puts the right article first for 85% of the test questions on the 8 codes, against 83% for the pretrained one. On the deployed 40-act index it is 83%: more acts, more competing articles. The version is fixed in a manifest with model revisions and a checkpoint hash."

**Slides 6–7 (40 s).** Name the services and what each stores. One Compose file, HTTPS by Caddy, the index built once on a GPU and copied.

**Slide 8.** Run the demo.

**Slide 9, performance (30 s).** "Ten users at once without any cache: 95% of searches finish within 1.2 seconds on a CPU; there were no errors, and one search in 981 came back without reranking."

**Slide 10, limits (40 s).** Read the slide. Do not soften it.

## Questions to prepare

**Did you train a model?** Yes: the reranker is a multilingual cross-encoder fine-tuned on 4,264 question–article pairs (Assignment 4). The embedder and the answer LLM are pretrained and used as they are.

**How much did fine-tuning help?** Offline +0.013 nDCG@10 (95% interval +0.003 to +0.025). Through the API two more questions in a hundred get the right article first. The classifier quality improved more: F1 0.60 → 0.65.

**Why is fine-tuning on fewer pairs better?** The full training set is 84% article titles, which are written in the statute's wording. Training only on the written questions matches how people ask.

**Why did the score drop on 40 acts?** The test questions were written for the 8 codes. Other acts regulate the same subjects, so there are more plausible articles. On the human-approved questions the result did not change.

**How do you know an answer is correct?** We do not, fully. The backend guarantees that every citation points to an article that was given to the LLM, and the user can open it. Whether the explanation follows from the text is not verified automatically.

**Are the test labels reliable?** They are automatic: the article a question was written for. A second correct article counts as an error, so the numbers are a lower bound in that respect; 7 of 60 reviewed questions were wrong or vague.

**Why is Kazakh weaker?** No Kazakh stemmer for keyword search, and the pretrained models saw little Kazakh. Kazakh training questions are the next step.

**Are the laws current?** The corpus is a snapshot of 17 September 2026.

**What happens when something is down?** Search falls back to PostgreSQL full-text search and marks the response; the reranker has a time budget and a circuit breaker; answers need the hosted LLM.

**How many users can it serve?** About 4 uncached searches per second on a laptop CPU; the reranker is 80% of a request. A GPU or an ONNX build of the reranker is the next lever.
