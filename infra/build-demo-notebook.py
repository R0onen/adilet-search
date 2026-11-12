"""Write a small API inference notebook for the final-project submission."""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
output = ROOT.parent / "Final Project/Final_Project_Demo.ipynb"
notebook = nbf.v4.new_notebook()
notebook.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
notebook.cells = [
    nbf.v4.new_markdown_cell(
        "# Adilet Search — final inference demonstration\n\n"
        "Run the Docker prototype first (`infra/start-final.ps1 -Index`). This notebook calls the "
        "real API; it does not use mocked responses or load credentials. The deployed E5 and "
        "cross-encoder models are pretrained. This is an integration demonstration, not evidence "
        "of our own fine-tuning or a human-gold quality benchmark.\n\n"
        "The current demo index covers the official Labor Code in RU/KK. See the readiness report "
        "for full-corpus, model-selection, load and public-hosting limitations."
    ),
    nbf.v4.new_code_cell('''import json
import urllib.request
from urllib.error import HTTPError

BASE_URL = "http://127.0.0.1:18000"

def api(path, payload=None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(BASE_URL + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)

health = api("/api/v1/health")
version = api("/api/v1/version")
assert health["status"] == "ok", health
assert version["pipeline_version"] == "0.2.0", version
print(json.dumps({"health": health, "version": version}, indent=2, ensure_ascii=False))'''),
    nbf.v4.new_markdown_cell("## New Russian and Kazakh questions\n\nCheck the retrieved articles and degradation flags. A correct result on these source-derived examples does not establish general accuracy."),
    nbf.v4.new_code_cell('''examples = [
    ("ru", "Какова нормальная продолжительность рабочего времени?", "K1500000414:ru:a68"),
    ("kk", "Жыл сайынғы ақы төленетін негізгі еңбек демалысының ұзақтығы қандай?", "K1500000414:kk:a88"),
]
for lang, question, expected in examples:
    result = api("/api/v1/search", {"query": question, "lang": lang, "mode": "hybrid", "top_k": 3})
    ids = [item["article"]["article_id"] for item in result["results"]]
    print(json.dumps({"language": lang, "query": question, "article_ids": ids, "expected_rank": ids.index(expected) + 1 if expected in ids else None, "degraded": result["degraded"]}, ensure_ascii=False, indent=2))
    assert ids and ids[0] == expected
    assert not result["degraded"]'''),
    nbf.v4.new_markdown_cell("## Inspect the stored source\n\nLegal text is retrieved verbatim. The dated snapshot does not establish that every later amendment is included."),
    nbf.v4.new_code_cell('''article = api("/api/v1/articles/K1500000414:ru:a68")
print(article["text"])
print("Official source:", article["article"]["url"])
assert "40" in article["text"]'''),
    nbf.v4.new_markdown_cell("## Stream an answer and validate reference IDs\n\nGeneration mode is a server setting: extractive fallback or an external OpenAI-compatible LLM. Check `final_runtime.json` for the actual mode. A valid citation reference is not proof that the source supports every claim."),
    nbf.v4.new_code_cell('''payload = {"query": examples[0][1], "lang": "ru"}
request = urllib.request.Request(BASE_URL + "/api/v1/answer", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
events = []
event = None
with urllib.request.urlopen(request, timeout=120) as response:
    for raw_line in response:
        line = raw_line.decode("utf-8").strip()
        if line.startswith("event: "):
            event = line[7:]
        elif line.startswith("data: "):
            events.append((event, json.loads(line[6:])))
sources = next(data["sources"] for event, data in events if event == "sources")
done = next(data for event, data in events if event == "done")
print(done["text"])
print("Citation references:", done["citations"])
print("Pipeline:", done["pipeline_version"])
assert set(done["citations"]) <= {source["ref"] for source in sources}
assert done["text"]'''),
    nbf.v4.new_markdown_cell("## Invalid input is rejected\n\nThe API should reject an empty question rather than attempting inference."),
    nbf.v4.new_code_cell('''try:
    api("/api/v1/search", {"query": ""})
except HTTPError as error:
    body = json.load(error)
    print(error.code, body["error"]["code"])
    assert error.code == 422
else:
    raise AssertionError("Empty question was accepted")'''),
]
nbf.write(notebook, output)
print(output)
