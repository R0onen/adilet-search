# ML defence: questions and answers

Numbers are from `docs/report/A3_report.md`, `A4_report.md`, `final_eval.md` and `load_test.md`.

1. **What is the ML task?** Ranking: for a question, order the articles of the corpus so that the one that answers it is first. The reranker is trained as a classifier of (question, article) pairs and scored as a ranker.

2. **Why nDCG@10 and not accuracy?** 95% of pairs are negative, so accuracy says little. nDCG@10 rewards the right article near the top, which is what the user and the answer generator see. We also report "right article first", MRR, recall, F1 and ROC-AUC.

3. **Where do the labels come from?** An LLM wrote two questions for each of 400 sampled articles; the article is the label. We reviewed 60 test questions by hand: 53 correct, 3 wrong, 4 too vague.

4. **How do you prevent leakage?** The split is by article, and the Russian and Kazakh versions of an article are in the same split. TF-IDF is fitted on the corpus, not on the questions. Thresholds and hyperparameters use training and validation data only. The notebook asserts that no article is in two splits.

5. **Which models did you compare?** BM25; Logistic Regression and SVM on lexical features; Logistic Regression and gradient boosting on E5 embeddings; a pretrained cross-encoder; the same cross-encoder with a trained head and fully fine-tuned; Qwen2.5-0.5B with LoRA.

6. **What was the largest improvement?** The pretrained cross-encoder: 0.867 nDCG@10 against 0.753 for the best embedding model, with no training on our data.

7. **What did fine-tuning add?** +0.013 nDCG@10 (p = 0.016) and a better classifier (F1 0.598 → 0.652, ROC-AUC 0.959 → 0.973). Through the live API, 85.1% against 83.1% "right article first".

8. **Why train on 4,264 pairs when you had 24,264?** The larger set is 84% article titles. Trained on it, the model got better on terminology questions and worse on everyday ones. The written questions alone gave an equal or better model in 2 minutes instead of 5.

9. **Why did LoRA lose?** A 0.5B general LLM with 0.1% of its parameters trained is not a match for a model pretrained specifically for passage ranking. It reached 0.805 and took 37 minutes.

10. **Why hybrid retrieval?** Keyword search finds exact terms and article numbers; the dense embedder finds articles that mean the same in other words. 15 of the reranker's 35 errors are articles BM25 never proposed, which is why the product retrieves with both.

11. **Why rerank only 5 candidates?** On a CPU 20 candidates take about a second and could not serve 10 users. Five keep most of the gain and give p95 1.2 s at 10 users.

12. **What is the dictionary for?** Words like "зарплата" or "вещдок" are not in the statutes. 34 such words get their legal terms appended to the query. It does not change the test-set score; it fixes everyday questions that returned unrelated articles.

13. **How is the answer kept honest?** The LLM sees only the retrieved articles and must cite them. The backend removes citations that do not point to a provided source and marks answers without valid citations. It cannot check that the cited article supports the claim.

14. **How good are the answers?** On 30 human-approved questions and 10 Kazakh ones: 38 answers were generated, and every answer cited a labelled article when it was among the sources (33 of 33). No citation pointed to a source that was not provided. The weak point: 11 answers opened with "the articles do not answer directly" although most of them then answered; the prompt was changed after that run. Nobody has judged the wording of each answer against the article.

15. **Why is Kazakh weaker?** No stemmer for keyword search, and the pretrained models saw little Kazakh: the reranker scores 0.83 nDCG@10 in Kazakh and 0.91 in Russian.

16. **Is the model version fixed?** Yes: `ml/models/model_manifest.json` records `pipeline_version` 1.0.0 and a pinned revision of every model. Our reranker is published as `qb2k/adilet-reranker-mminilm-ru-kk` on the Hugging Face Hub, so a fresh checkout downloads exactly the weights we evaluated.

17. **What happens when the law changes?** Download the new snapshot, rebuild the corpus, index into a new collection and switch the alias. The models do not need retraining for new text.

18. **Does it work on the acts added later?** Less well. On 55 everyday questions about them the right article is first for 58% and in the top 10 for 87%, against 26% and 64% for keyword search. The reranker was trained on the 8 codes only, and these questions are more colloquial.

19. **What would you do next?** Kazakh training questions; a gold set written by lawyers; a faster reranker (ONNX or a GPU) so that more candidates can be reranked.
