"""Build the 10-slide final presentation: `final_deck.pptx` and `final_deck.md` next to this file.

    python docs/presentation/build_final.py        (needs python-pptx)

Every number on the slides is copied from a report in this repository; the speaker notes of each
slide name the source. Change the text in SLIDES and run the script again.
"""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

HERE = Path(__file__).resolve().parent
NAVY, WHITE, MUTED, TEAL, PANEL = "102B46", "FFFFFF", "A9BED0", "78E1C6", "1D405D"

PUBLIC_URL = "Live demo: https://bacterium-margarita-coveted.ngrok-free.dev"

EXPERIMENTS = [
    ("Model", "Kind", "nDCG@10", "ROC-AUC"),
    ("BM25, tuned", "classical", "0.697", "–"),
    ("TF-IDF features + Logistic Regression", "classical", "0.727", "0.923"),
    ("E5 embedding + lexical features + boosting", "embeddings + ML", "0.753", "0.953"),
    ("Qwen2.5-0.5B + LoRA", "LoRA", "0.805", "0.951"),
    ("Cross-encoder, pretrained", "transfer", "0.867", "0.959"),
    ("Cross-encoder, fine-tuned (served)", "fine-tuning", "0.880", "0.973"),
]

FINAL = [
    ("Index", "Reranker", "Right article first", "nDCG@10"),
    ("8 codes", "pretrained", "83.1%", "0.885"),
    ("8 codes", "fine-tuned", "85.1%", "0.895"),
    ("40 acts (deployed)", "fine-tuned", "82.6%", "0.871"),
]

ARCHITECTURE = [
    (0.7, 2.7, 3.1, "React UI\nsearch, answer, article viewer, admin"),
    (5.1, 2.7, 3.1, "FastAPI\nsearch and answer API, query log"),
    (9.5, 2.7, 3.1, "ML service\nE5, fine-tuned reranker, LLM client"),
    (2.9, 4.7, 3.1, "PostgreSQL\narticles, logs, full-text fallback"),
    (7.3, 4.7, 3.1, "Qdrant\ndense + sparse index"),
]

# (label, title, body, speaker notes)
SLIDES = [
    (
        "01 / PROBLEM",
        "Find the law behind the question",
        "People ask in everyday words; the law answers in its own.\n"
        "Adilet Search: a question in Russian or Kazakh → the articles that answer it, "
        "and a short answer that cites them.",
        "Built as the AI module of the Legal Service platform. Keyword search finds an article only "
        "when the question uses its words: 'задерживают зарплату' does not occur in the Labor Code, "
        "'сроки выплаты заработной платы' does. The system is a search aid, not legal advice.",
    ),
    (
        "02 / DATASET",
        "Official texts and 803 test questions",
        "Corpus: AdiletCodex v1.0 (adilet.zan.kz), snapshot of 17 September 2026\n"
        "Deployed: 40 acts · 20,490 articles in Russian and Kazakh · 41,074 chunks\n"
        "Experiments: 8 codes · 9,259 articles\n"
        "Questions: 803 written by an LLM for 400 articles, split by article 70 / 15 / 15\n"
        "A person checked 60 of the 195 test questions: 53 correct",
        "Sources: ml/MODEL_CARD.md, data/eval/synthetic/meta.json, "
        "data/eval/labeling/synthetic_review_summary.json. Texts are stored verbatim. Each question has "
        "one labelled article (the one it was written for); no article is in two splits. The review "
        "found 3 wrong and 4 too vague questions out of 60. There is no gold set written by lawyers.",
    ),
    (
        "03 / MODEL",
        "Retrieve, rerank, then answer from the sources",
        "1. Everyday words → legal terms (dictionary)\n"
        "2. Dense search (multilingual E5) + keyword search (BM25)\n"
        "3. Reciprocal-rank fusion of the two lists\n"
        "4. Cross-encoder reranker, fine-tuned on our questions\n"
        "5. LLM writes an answer from the top articles and cites them [1], [2]",
        "Embedder: intfloat/multilingual-e5-base, pretrained. Reranker: "
        "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1, fine-tuned by us (Assignment 4). The backend "
        "removes citations that do not point to a provided source. If the models or the vector index "
        "are down, search falls back to PostgreSQL full-text search.",
    ),
    (
        "04 / EXPERIMENTS",
        "From keywords to a fine-tuned transformer",
        "",
        "Task: rerank 20 BM25 candidates for 195 test questions; the ceiling is 0.923. Sources: "
        "docs/report/A3_report.md, docs/report/A4_report.md, executed notebooks in ml/notebooks/. "
        "The pretrained cross-encoder is the largest step (+0.114 over the best embedding model, "
        "p < 0.001). Fine-tuning on the 4,264 pairs from written questions adds +0.013 "
        "(95% interval +0.003 to +0.025, p = 0.016) and improves the classifier (F1 0.598 → 0.652). "
        "LoRA on a small general LLM is below the cross-encoder and 7 times slower to train. A "
        "separate comparison of embedding models (BGE-M3, Qwen3, EmbeddingGemma) on title queries is "
        "in docs/report/RESEARCH_FINDINGS.md.",
    ),
    (
        "05 / FINAL MODEL",
        "Pipeline 1.0.0, measured through the live API",
        "",
        "Source: ml/experiments/final-selection/. Hybrid mode, 5 reranked candidates, 195 test "
        "questions. On the 53 human-approved questions the right article is first for 83.0% on both "
        "indexes. Adding 32 acts costs 2.5 points on questions written for the 8 codes, because other "
        "acts regulate the same subjects. The version is fixed in ml/models/model_manifest.json "
        "with pinned model revisions; the reranker is published on the Hugging Face Hub. Inputs and outputs: contracts/api.md.",
    ),
    (
        "06 / ARCHITECTURE",
        "One API between the UI and the models",
        "",
        "Docker Compose: frontend (nginx), backend (FastAPI), ML service, PostgreSQL, Qdrant, Caddy "
        "for HTTPS, Prometheus and Grafana. The interfaces are fixed in contracts/. The admin panel "
        "shows usage, the query log, health and reindexing.",
    ),
    (
        "07 / DEPLOYMENT",
        "One command on a small server",
        "docker compose -f docker-compose.prod.yml up -d\n"
        "Only the proxy's port is open; HTTPS from Caddy on a server or from an ngrok tunnel\n"
        "The index is built once on a GPU and copied to the server\n" + PUBLIC_URL,
        "The live demo runs this stack on a team machine behind an ngrok tunnel; the first visit shows "
        "ngrok's warning page (click Visit Site). Guide: docs/tech/deployment.md; sizing: docs/tech/infrastructure_sizing.md. CI runs unit, "
        "contract and integration tests, a dependency audit and a full-stack smoke test on every pull "
        "request.",
    ),
    (
        "08 / DEMONSTRATION",
        "Ask, read the article, check the answer",
        "«Работодатель задерживает зарплату — что делать?»\n"
        "«Можно ли вернуть товар в магазин без чека?»\n"
        "«Жұмыс уақытының қалыпты ұзақтығы қандай?»\n"
        "Open a cited article · switch Russian ↔ Kazakh · admin panel",
        "Script: docs/presentation/demo_script.md. Show the ranked articles first, then the generated "
        "answer and its citations, then the full article text. Show a question the corpus does not "
        "answer: the answer says so and reports what the articles do say.",
    ),
    (
        "09 / PERFORMANCE",
        "Fast enough for 10 users at once",
        "Load test: 10 users at once, cache off, 40-act index, CPU only\n"
        "981 searches · no errors · 1 answered without reranking (0.1%)\n"
        "p50 0.65 s · p95 1.2 s · target p95 ≤ 2 s\n"
        "One search alone: about 0.35 s\n"
        "Answers: 40 of 40 generated, each cites the right article when retrieved; first words after 0.7 s",
        "Source: docs/report/load_test.md (10 simulated users, cache off, every request through "
        "embedding, retrieval and reranking, 5 minutes). Tests: backend unit, contract and "
        "integration tests, ML tests, frontend tests; counts in docs/report/final_readiness.md. Answers: "
        "docs/report/final_eval.md (30 human-approved questions and 10 Kazakh ones, hosted LLM).",
    ),
    (
        "10 / LIMITS AND NEXT STEPS",
        "What the numbers do not show",
        "Test questions are LLM-written; 60 were checked by a person, none by a lawyer\n"
        "Kazakh is weaker than Russian (reranker nDCG@10 0.83 against 0.91)\n"
        "Everyday questions on the added acts: right article first for 58%, not 83%\n"
        "15 of 35 reranker errors: the article never reaches the reranker\n"
        "The corpus is a snapshot; later amendments are not in it\n"
        "Next: Kazakh training questions, a larger dictionary, a lawyer-written gold set",
        "Sources: docs/report/A4_report.md (error analysis), ml/MODEL_CARD.md (limits). The generator "
        "can misread a source; the backend checks that citations point to provided sources, not that "
        "the source supports the claim.",
    ),
]


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
    frame = shape.text_frame
    frame.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        paragraph.text = line
        paragraph.font.name = "Aptos"
        paragraph.font.size = Pt(size)
        paragraph.font.bold = bold
        paragraph.font.color.rgb = RGBColor.from_string(color)
        paragraph.space_after = Pt(8)
    return shape


def table(slide, rows, widths, top=2.5, size=18):
    x = 0.7
    for column, width in enumerate(widths):
        for r, row in enumerate(rows):
            last = r == len(rows) - 1
            box(
                slide,
                x,
                top + 0.52 * r,
                width,
                0.5,
                row[column],
                size,
                TEAL if r == 0 or last else WHITE,
                bold=r == 0 or last,
            )
        x += width


def markdown_table(rows):
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])]
    return "\n".join(lines + ["| " + " | ".join(row) + " |" for row in rows[1:]])


def main():
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    md = ["---", "marp: true", "paginate: true", "---", ""]
    for i, (label, title, body, notes) in enumerate(SLIDES):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = RGBColor.from_string(NAVY)
        box(slide, 0.65, 0.45, 11.8, 0.4, label, 13, TEAL, bold=True)
        box(slide, 0.65, 1.0, 11.8, 1.2, title, 36, bold=True)
        if i == 3:
            table(slide, EXPERIMENTS, [5.8, 2.8, 1.7, 1.7])
            caption = "195 test questions · reranking 20 candidates · ceiling 0.923"
            box(slide, 0.7, 6.25, 11.6, 0.4, caption, 14, TEAL)
            body = markdown_table(EXPERIMENTS) + "\n\n" + caption
        elif i == 4:
            table(slide, FINAL, [3.6, 2.6, 3.2, 2.0], top=2.6, size=20)
            caption = (
                "Fine-tuned against pretrained: +0.013 nDCG@10 offline, p = 0.016\n"
                "Human-approved questions: right article first for 83.0%\n"
                "55 everyday questions on the added acts: first 58%, top 10 87% "
                "(keyword search: 26%, 64%)"
            )
            box(slide, 0.7, 4.9, 11.6, 1.6, caption, 19)
            body = markdown_table(FINAL) + "\n\n" + caption
        elif i == 5:
            for x, y, w, text in ARCHITECTURE:
                box(slide, x, y, w, 1.2, text, 17, fill=PANEL)
            box(slide, 4.05, 2.95, 0.8, 0.6, "→", 28, TEAL)
            box(slide, 8.45, 2.95, 0.8, 0.6, "→", 28, TEAL)
            box(slide, 5.6, 4.0, 2.1, 0.5, "↓          ↓", 25, TEAL)
            footer = "Caddy (HTTPS) in front · Prometheus → Grafana behind"
            box(slide, 0.7, 6.2, 11, 0.4, footer, 16, TEAL)
            body = "\n".join(text.replace("\n", ": ") for *_, text in ARCHITECTURE) + "\n" + footer
        elif i == 7 and (HERE / "img/final-live.png").exists():
            box(slide, 0.65, 2.5, 5.4, 4.0, body, 19)
            slide.shapes.add_picture(
                str(HERE / "img/final-live.png"), Inches(6.4), Inches(2.35), width=Inches(6.3)
            )
        else:
            box(slide, 0.65, 2.4, 11.8, 3.8, body, 23)
        if i == 0:
            names = "Daniil Talyzin  ·  Yernur Kazhyakpar  ·  Kuanysh Murat"
            box(slide, 0.65, 5.6, 11.8, 0.6, names, 17, TEAL)
        box(slide, 0.65, 6.85, 10.5, 0.3, "ADILET SEARCH  /  FINAL PROJECT", 10, MUTED)
        box(slide, 11.8, 6.8, 0.8, 0.4, f"{i + 1:02d}/{len(SLIDES)}", 12, TEAL)
        slide.notes_slide.notes_text_frame.text = notes
        md += (["---", ""] if i else []) + [
            f"# {title}",
            "",
            body.replace("\n", "\n\n") if "|" not in body else body,
            "",
            f"<!-- {notes} -->",
            "",
        ]
    deck.save(HERE / "final_deck.pptx")
    (HERE / "final_deck.md").write_text("\n".join(md), encoding="utf-8", newline="\n")
    print(f"Built {len(deck.slides)} slides: {HERE / 'final_deck.pptx'}")


if __name__ == "__main__":
    main()
