# ML Defence Q&A

1. Why nDCG@10?  
It rewards relevant articles near the top, which is what users and RAG context selection need.

2. Why not accuracy?  
Retrieval has many negatives and ranking order matters more than a binary decision.

3. Why hybrid retrieval?  
BM25 protects exact article/legal-term queries; dense retrieval should help paraphrases once real
embeddings are enabled.

4. What is the current final model?  
`0.1.0-bootstrap`, an integration-ready offline pipeline.

5. Is it production quality?  
No. It needs official corpus parsing, human labels and real model checkpoints.

6. Why QLoRA instead of full fine-tuning?  
A full 7B fine-tune needs much more GPU memory; QLoRA fits student GPU environments and stores a
small adapter.

7. How are citations controlled?  
The prompt requires numbered sources, and backend citation validation removes invalid markers.

8. What happens when the law changes?  
Re-scrape, bump `corpus_version`, rebuild embeddings, reindex into a new collection and switch the
alias after evaluation.

9. How is leakage prevented?  
Splits group RU/KK article variants by `doc_id:unit_key`.

10. What is the Kazakh limitation?  
Kazakh tokenization is simple and needs native-speaker review plus real labels.

11. Why is BM25 strongest now?  
The seed sample is tiny and queries share exact terms with the relevant articles.

12. What would improve first?  
Official corpus parsing and gold labels, then real E5/BGE embeddings and cross-encoder reranking.

13. How are model versions tracked?  
`pipeline_version` tracks served behavior; `index_compat_id` changes when embeddings/indexes must
be rebuilt.

14. What proves reproducibility?  
Each experiment folder has `config.yaml`, `metrics.json` and `env.json`; `results.csv` is generated
from those folders.

15. What remains blocked?  
HF credentials, live scraping approval, human labels, GPU fine-tuning and deployed API evaluation.
