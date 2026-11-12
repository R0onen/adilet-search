# Technical documentation

- [Final-project deployment and checks](final_project.md): the current startup and validation path.
- [Research comparison](research_benchmark.md): recent models, frozen-split evaluation and reproduction.
- [ML](ml.md): retrieval and serving implementation; consult the current model card for identity.
- [Frontend](frontend.md): UI architecture and API integration.
- [Public API](../../contracts/api.md): request/response and SSE contracts.
- [Internal ML API](../../contracts/ml_service.md): embedding, reranking and generation contracts.
- [Data schema](../../contracts/data_schema.md): corpus and evaluation records.
- [Model card](../../ml/MODEL_CARD.md): pinned pipeline, data and limits.
- [Readiness report](../report/final_readiness.md): current evidence and open gaps.
- [Final deck](../presentation/final_deck.md): presentation text and source notes.
- [Speaker guide](../presentation/final_speaker_guide.md): rehearsal and Q&A.

Local prototype: http://127.0.0.1:18080. Public HTTPS deployment is pending.
Model weights are pulled by their pinned public Hugging Face model IDs in the manifest;
no project-owned trained-model repository or completed fine-tuning run is linked yet.
