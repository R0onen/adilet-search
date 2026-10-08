# Contract changelog

Append-only, newest first. Each entry: **date · contract · version · breaking? · who must react**, then what changed and why.

Process (from `CLAUDE.md`):
1. The owner edits the contract.
2. The owner appends an entry here.
3. The owner notes it in their status file.
4. A human relays it to the affected agents.

Breaking changes need the affected owner's OK before merging.

---

## 2026-10-05 · api.md, ml_service.md, data_schema.md · v1 · — · everyone

Initial contracts, written during planning. Expect small additive adjustments in week 1, while the agents scaffold. After gate G0, every change follows the process above.

Open items to settle by G0:
- **Backend:** confirm that the `/answer` SSE event shapes are implementable as written with sse-starlette.
- **ML:** confirm the `text_for_embedding` header format after seeing real KK pages, and whether adilet article anchors are stable enough for `source_url`.
- **Frontend:** confirm that the `/admin/stats` fields cover the dashboard design.
