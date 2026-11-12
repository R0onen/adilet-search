"""Build the evidence-bounded, editable 10-slide final presentation.

Run with a Python environment containing python-pptx. Results come from the CSV;
pending measurements are explicitly labelled. No network requests or credentials.
"""
import csv
import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT.parent / "Final Project"
NAVY, WHITE, MUTED, TEAL = "102B46", "FFFFFF", "A9BED0", "78E1C6"


def box(slide, x, y, w, h, text, size=22, color=WHITE, fill=None, bold=False):
    if fill:
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill)
        shape.line.fill.background()
    else:
        shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.name = "Aptos"
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = RGBColor.from_string(color)
        p.space_after = Pt(10)
    return shape


def main():
    rows = list(csv.DictReader((ROOT / "ml/reports/results.csv").open(encoding="utf-8")))
    row = next(r for r in rows if r["run"] == "20261111_bm25_title_test")
    manifest = json.loads((ROOT / "ml/models/model_manifest.json").read_text(encoding="utf-8"))
    data = [
        ("01 / PROBLEM", "Find the law behind the question",
         "Adilet Search · Kazakhstan legislation\nRussian and Kazakh questions → articles with sources",
         "Keyword search misses everyday wording. Our prototype combines lexical and semantic retrieval, then can generate a source-cited answer. Team: Daniil Talyzin, Yernur Kazhyakpar, Kuanysh Murat. This is a course prototype for the Legal Service use case; production integration is not claimed. Source: README.md; docs/PROJECT_PLAN.md §1."),
        ("02 / DATASET", "Official text, a bounded snapshot",
         "8 Tier-1 code documents · RU + KK\n9,259 article-language records · 16,264 chunks\nSnapshot: 17 September 2026",
         "AdiletCodex v1.0, CC BY 4.0; see ml/MODEL_CARD.md and ml/scripts/download_data.py. A fresh rebuild reproduced 16 document-language rows, 9,259 articles and 16,264 chunks. These counts include both languages; do not say 9,259 distinct bilingual articles. Text is preserved; amendment notes are separate. The snapshot does not establish current legal validity."),
        ("03 / MODEL", "Retrieve first, generate from sources",
         "BM25 + multilingual E5\nReciprocal-rank fusion → cross-encoder\nOptional LLM → validated citation references",
         "Dense model: intfloat/multilingual-e5-base; reranker: cross-encoder/mmarco-mMiniLMv2-L12-H384-v1. Both pretrained, zero-shot on this project. RRF k=60, equal weights. An external OpenAI-compatible generator is configurable; the default fallback extracts a sentence. Citation reference validation does not prove that the source supports the answer. Source: ml/models/model_manifest.json; ml/MODEL_CARD.md."),
        ("04 / EXPERIMENTAL RESULTS", "A measured lexical baseline",
         f"BM25 · {int(row['queries']):,} held-out title queries\nnDCG@10  {float(row['ndcg@10']):.3f}     Recall@50  {float(row['recall@50']):.3f}\nProxy evaluation · article-body search",
         f"Source: ml/reports/results.csv, run {row['run']}. MRR@10={float(row['mrr@10']):.3f}, Recall@10={float(row['recall@10']):.3f}. RU nDCG@10={float(row['ru_ndcg@10']):.3f}; KK={float(row['kk_ndcg@10']):.3f}. Title queries are generated from headings and are not human natural-language gold labels. No measured superiority of dense/hybrid/reranked retrieval or fine-tuning is claimed."),
        ("05 / FINAL MODEL", f"Versioned pipeline {manifest['pipeline_version']}",
         "Pinned embedder and reranker revisions\nInput: RU/KK query + retrieval context\nOutput: ranked articles; optional cited answer",
         "The current candidate is pipeline 0.2.0, not a final winner selected by comparable experiments. index_compat_id=e5base-bm25st-ch1. Query and passage prefixes and dimensions are in the manifest. The service loads saved pretrained weights; no team-trained checkpoint is evidenced. Generator identity is deployment-specific. Before submission, compare candidates on a common validation set and freeze the choice; do not change this slide to claim training without run artifacts."),
        ("06 / SYSTEM ARCHITECTURE", "One API joins retrieval and the UI",
         "React UI → FastAPI API\nPostgreSQL + Qdrant + ML service\nPrometheus → Grafana",
         "Search: embed query, dense/sparse retrieval, RRF fusion, article collapse, cross-encoder rerank. Answer: retrieve sources, stream generation via SSE, validate citation references. Frontend source drawer supports RU/KK. Architecture sources: docker-compose.yml; docker-compose.final.yml; backend/app/state.py; frontend/src/App.tsx. Monitoring additions require runtime verification; planned components must not be described as deployed until that succeeds."),
        ("07 / DEPLOYMENT", "A reproducible container deployment",
         "Docker Compose + isolated persistent volumes\nFrontend serves UI and proxies streaming API\nPublic HTTPS hosting: pending",
         "Use docs/tech/final_project.md. Local build and public hosting are separate claims. An accessible local demonstration is the immediate target; the project plan also asks for public HTTPS. There is no verified public URL in the repo. Do not expose admin stubs or database ports to the public internet. No VPS purchase or account action is performed by this script."),
        ("08 / DEMONSTRATION", "Follow the answer back to the article",
         "Ask about working hours or annual leave\nInspect ranked articles and exact source text\nSwitch RU ↔ KK; compare keyword and hybrid",
         "Rehearse using the actual indexed corpus. Start with 'Какова нормальная продолжительность рабочего времени?' and 'Сколько дней ежегодного оплачиваемого отпуска?'. Confirm the retrieved sources before showing generation. Current local generation uses externally pretrained openai/gpt-oss-120b; a fresh checkout defaults to extractive fallback. Try an unsupported question and show the limitation. Prepare a backup recording only after a successful live rehearsal. Sources: docs/presentation/demo_script.md; frontend/src/App.tsx."),
        ("09 / PERFORMANCE", "Measure quality and system speed separately",
         "Quality: BM25 proxy baseline available\nSystem: p50/p95 + failures under load\nSearch target: p95 ≤ 2 s at 10 users",
         "The latency target is from docs/PROJECT_PLAN.md §8 and is not a measured result. Current checks: 49 ML, 258 backend unit/contract, 34 storage/integration and 6 real-ML checks; 12 frontend unit tests and 4 browser scenarios. Updated totals and runtime results belong in docs/report/final_readiness.md. Measure non-degraded coverage, error rate, model IDs and hardware alongside latency. A fast degraded response is not evidence that full semantic search met the target."),
        ("10 / LIMITATIONS & FUTURE WORK", "The next step is stronger evidence",
         "Human-labelled RU/KK relevance benchmark\nFair model comparison and training evidence\nDeployment, load testing and source faithfulness",
         "No legal Kazakh fine-tuning is evidenced. The reranker training includes Russian, not Kazakh. There is no human gold benchmark. Citation validity differs from factual support. The dated corpus may omit later amendments. Admin endpoints are stubs in the inspected source. Finish monitoring validation, public hosting, real-model evaluation and native-speaker review before claiming the full planned system. Source: ml/MODEL_CARD.md; docs/status/*.md; backend/app/api/v1/admin/*.py."),
    ]
    # Update the presentation from the latest recorded runtime evidence.
    load_path = ROOT / "docs/report/final_load.json"
    if load_path.exists():
        load = json.loads(load_path.read_text(encoding="utf-8"))
        label, title, _, notes = data[8]
        p95 = load.get("full_p95_ms")
        latency = f"{p95:,.0f} ms" if p95 is not None else "not available"
        data[8] = (
            label, "Load testing exposes the CPU limit",
            f"{load['requests']} requests · {load['users']} concurrent users\n"
            f"HTTP errors: {load['http_errors']} · degraded: {load['degraded_responses']}\n"
            f"Complete-response p95: {latency} · target {'met' if load['target_met'] else 'not met'}",
            notes + " Latest source: docs/report/final_load.json. This is a repeated-question "
            "sample-corpus load test. No full-corpus generalization is claimed.",
        )
    data[6] = (
        data[6][0], "The prototype runs in Docker",
        "Live UI + API + real model inference\nPrometheus targets up · Grafana healthy\nLocal access verified · public HTTPS pending",
        data[6][3] + " Verified in this session: UI http://127.0.0.1:18080, API proxy, "
        "source drawer and RU/KK switch. Source: docs/report/final_browser.json.",
    )
    research = None
    for kind in ("final", "full", "pilot"):
        candidate = ROOT / f"ml/experiments/research-{kind}/results.json"
        if candidate.exists():
            value = json.loads(candidate.read_text(encoding="utf-8"))
            if {"e5", "qwen3", "bge_m3", "current_hybrid_reranker"} <= set(value["methods"]):
                research = value
                break
    if research:
        pilot = bool(research["pilot_per_language"])
        scope = "Exploratory pilot" if pilot else "Frozen validation/test proxy study"
        source = "Research sources: docs/report/RESEARCH_PROTOCOL.md; ml/experiments/research-*/results.json. Title-derived proxy labels, not human gold."
        data[2] = (data[2][0], "Test models, fusion and LLM rewriting",
                   "Does a newer embedder improve retrieval?\nDoes hybrid reranking help RU and KK?\nDoes an LLM rewrite justify its extra cost?", source)
        data[3] = (data[3][0], "Newer models must earn their place",
                   scope + " · body-only corpus\nnDCG@10 by split and language\nSame questions, chunks and token budget", source)
        metric_table = ["| Method | Val nDCG@10 | Test nDCG@10 | RU | KK |",
                        "|---|---:|---:|---:|---:|"]
        for name, method in research['methods'].items():
            scores = [method['splits'][key]['ndcg@10'] for key in
                      ('val:all', 'test:all', 'test:ru', 'test:kk')]
            metric_table.append('| ' + name + ' | ' + ' | '.join(f'{v:.3f}' for v in scores) + ' |')
        data[3] = (data[3][0], data[3][1], '\n'.join(metric_table),
                   source + ' Full corpus: 16,264 body-only chunks. Validation: 1,311; test: 1,318. '
                   'Same 512-token budget, language filtering and article collapse. The hybrid '
                   'reproduction uses local BM25, RRF k=60 equal weights and top-20 reranking; '
                   'Qdrant IDF differs. Scores compare practical pretrained configurations; '
                   'no project-specific fine-tuning or isolated architecture effect is claimed.')
        data[4] = (data[4][0], "Choose by validation and inspect failures",
                   "Validation candidate: " + research["validation_winner"] +
                   "\nPinned checkpoints · paired article-family bootstrap\nIndependent natural-language evaluation still needed", source)
        winner = research['validation_winner']
        interval = research.get('paired_test_ndcg10_delta_vs_e5', {}).get(winner)
        if interval:
            lo, hi = interval['ci95']
            data[4] = (data[4][0], "Hybrid remains the measured candidate",
                       f"Hybrid − E5 test nDCG@10: {interval['mean']:+.3f}\n"
                       f"Paired 95% interval: [{lo:+.3f}, {hi:+.3f}]\n"
                       "LLM rewrite: small pilot; no benefit established",
                       source + " Validation selects the candidate; test estimates performance. "
                       "Intervals group parallel RU/KK article families. This is a fixed-cohort "
                       "proxy study; no multiple-comparison correction or human-gold claim. "
                       "EmbeddingGemma 2 uses supported BF16, other embedding models FP16. "
                       "The served pipeline remains version 0.2.0: multilingual-e5-base plus "
                       "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, with pinned checkpoints. "
                       "See RESEARCH_FINDINGS.md and ml/models/model_manifest.json.")
        data[9] = (data[9][0], "The next step is stronger evidence",
                   "Independent human-labelled RU/KK questions\n"
                   "Long-context and prompt-sensitivity experiments\n"
                   "Scale LLM pilot; measure faithfulness and API load",
                   "The full frozen proxy experiment now compares recent pretrained models. "
                   "No project-specific fine-tuning is claimed. Do not generalize title-query "
                   "metrics to legal advice or generated-answer correctness. Public hosting "
                   "and CPU load acceptance remain outstanding. " + source)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    md = ["---", "marp: true", "paginate: true", "---", ""]
    for i, (label, title, body, notes) in enumerate(data):
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string(NAVY)
        box(slide, .65, .45, 11.8, .4, label, 13, TEAL, bold=True)
        box(slide, .65, 1.15, 11.8, 1.2, title, 36, bold=True)
        if i == 3 and research:
            columns = [(0.8, 4.5, "Method"), (5.4, 1.6, "Val"), (7.1, 1.6, "Test"),
                       (8.8, 1.6, "RU test"), (10.5, 1.6, "KK test")]
            for x, w, label_text in columns:
                box(slide, x, 2.6, w, .5, label_text, 18, TEAL, bold=True)
            labels = {"e5": "E5 baseline", "hybrid_no_reranker": "Hybrid without reranking", "qwen3": "Qwen3 Embedding 0.6B", "bge_m3": "BGE-M3", "embeddinggemma2": "EmbeddingGemma 2 (Oct 2026)",
                      "current_hybrid_reranker": "Project hybrid + reranker", "e5_llm_rewrite": "E5 + LLM query rewrite"}
            for r, (name, method) in enumerate(research["methods"].items()):
                values = [labels.get(name, name)] + [f"{method['splits'][key]['ndcg@10']:.3f}" for key in
                    ("val:all", "test:all", "test:ru", "test:kk")]
                for (x, w, _), value in zip(columns, values):
                    box(slide, x, 3.15 + .43*r, w, .4, value, 16)
            n = research["methods"]["e5"]["splits"]["test:all"]["queries"]
            box(slide, .8, 6.05, 11.6, .5, f"{'PILOT' if research['pilot_per_language'] else 'PROXY STUDY'} · {n} test queries · title-derived labels · nDCG@10", 14, TEAL)
        elif i == 5:
            for x, y, w, text in [
                (.7, 2.8, 3.1, "React UI\nSearch + source viewer"),
                (5.1, 2.8, 3.1, "FastAPI\nSearch + answer API"),
                (9.5, 2.8, 3.1, "ML service\nE5 + reranker"),
                (3.3, 4.8, 3.1, "PostgreSQL\nArticles + query logs"),
                (7.2, 4.8, 3.1, "Qdrant\nDense + sparse index"),
            ]:
                box(slide, x, y, w, 1.1, text, 18, fill="1D405D")
            box(slide, 4.05, 3.08, .8, .6, "→", 28, TEAL)
            box(slide, 8.45, 3.08, .8, .6, "→", 28, TEAL)
            box(slide, 5.6, 4.05, 2.1, .5, "↓          ↓", 25, TEAL)
            box(slide, .7, 6.12, 11, .4, "OBSERVABILITY   Prometheus → Grafana", 16, TEAL)
        elif i == 7 and (HERE / "img/final-live.png").exists():
            box(slide, .65, 2.65, 4.2, 3.5, body, 23)
            slide.shapes.add_picture(str(HERE / "img/final-live.png"), Inches(5.3), Inches(2.6), width=Inches(7.3))
        else:
            box(slide, .65, 2.65, 11.8, 2.65, body, 26)
        if i == 0:
            box(slide, .65, 5.6, 11.8, .6, "Daniil Talyzin  ·  Yernur Kazhyakpar  ·  Kuanysh Murat", 17, TEAL)
        box(slide, .65, 6.78, 10.5, .3, "ADILET SEARCH  /  AI ESSENTIALS  /  EVIDENCE DRAFT", 10, MUTED)
        box(slide, 11.8, 6.75, .8, .4, f"{i+1:02d}/10", 12, TEAL)
        slide.notes_slide.notes_text_frame.text = notes
        if i == 3 and not research:
            # Compact language comparison with a shared 0–1 scale.
            for j, (lang, key) in enumerate([("RU", "ru_ndcg@10"), ("KK", "kk_ndcg@10")]):
                v = float(row[key])
                box(slide, .8 + j * 6, 5.55, 1.2, .4, lang, 16, TEAL)
                box(slide, 1.8 + j * 6, 5.55, 3.8 * v, .4, "", fill=TEAL)
                box(slide, 4.85 + j * 6, 5.5, 1, .5, f"{v:.3f}", 16)
        md += (["---", ""] if i else []) + [f"# {title}", "", body.replace("\n", "\n\n"), "", f"<!-- {notes} -->", ""]
    OUT.mkdir(exist_ok=True)
    prs.save(HERE / "final_deck.pptx")
    prs.save(OUT / "Adilet_Search_Final.pptx")
    (HERE / "final_deck.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Built {len(prs.slides)} slides: {OUT / 'Adilet_Search_Final.pptx'}")


if __name__ == "__main__":
    main()
