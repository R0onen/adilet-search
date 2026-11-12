"""The two manifests and the answer prompt that the service ships with."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from adilet_ml.schemas import GenerateRequest, Manifest
from adilet_ml.serving import engine
from adilet_ml.serving.engine import (
    CrossEncoderReranker,
    HashEmbedder,
    LexicalReranker,
    SentenceTransformerEmbedder,
    build_messages,
)

MODELS = Path(__file__).parents[1] / "models"


@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_both_neural_stages_use_the_explicit_device(
    device: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    devices = []

    class FakeModel:
        def __init__(self, *args, **kwargs):
            devices.append(kwargs["device"])

    monkeypatch.setenv("ADILET_ML_DEVICE", device)
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=FakeModel, CrossEncoder=FakeModel),
    )
    SentenceTransformerEmbedder("test", 768)
    CrossEncoderReranker("test")
    assert devices == [device, device]


def load(name: str) -> Manifest:
    return Manifest.model_validate(json.loads((MODELS / name).read_text(encoding="utf-8")))


def test_real_manifest_pins_real_models() -> None:
    manifest = load("model_manifest.json")
    assert manifest.embedder.runtime == "sentence-transformers"
    assert manifest.reranker.runtime == "cross-encoder"
    for info in (manifest.embedder, manifest.reranker):
        assert len(info.revision) == 40  # a commit hash, not a branch name
    assert "bootstrap" not in manifest.pipeline_version


def test_bootstrap_manifest_is_offline_and_has_its_own_index_compat_id() -> None:
    real, boot = load("model_manifest.json"), load("model_manifest.bootstrap.json")
    assert boot.pipeline_version.endswith("-bootstrap")
    assert boot.index_compat_id != real.index_compat_id  # a hash index is never served as E5
    assert isinstance(engine._build_embedder(boot), HashEmbedder)
    assert isinstance(engine._build_reranker(boot), LexicalReranker)
    assert boot.sparse.model_dump() == real.sparse.model_dump()


def test_manifest_runtime_selects_the_cross_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, object] = {}

    def fake_init(self: object, model_name: str, max_seq_len: int, revision: str | None) -> None:
        created.update(model=model_name, max_seq_len=max_seq_len, revision=revision)

    monkeypatch.setattr(CrossEncoderReranker, "__init__", fake_init)
    manifest = load("model_manifest.json")
    assert isinstance(engine._build_reranker(manifest), CrossEncoderReranker)
    assert created == {
        "model": manifest.reranker.hf_repo,
        "max_seq_len": manifest.reranker.max_seq_len,
        "revision": manifest.reranker.revision,
    }


def test_prompt_has_system_rules_and_numbered_sources() -> None:
    body = GenerateRequest.model_validate(
        {
            "question": "Сколько дней отпуска?",
            "lang": "kk",
            "sources": [
                {
                    "ref": 1,
                    "article_id": "K1500000414:ru:a88",
                    "title": "ТК РК. Статья 88",
                    "text": "24 календарных дня.",
                }
            ],
        }
    )
    system, user = build_messages(body)
    assert system["role"] == "system"
    assert "В предоставленных источниках нет ответа." in system["content"]
    assert "Берілген дереккөздерде жауап жоқ." in system["content"]
    assert "no Markdown" in system["content"]
    assert user["role"] == "user"
    assert "Language: Kazakh" in user["content"]
    assert "[1] ТК РК. Статья 88\n24 календарных дня." in user["content"]
    assert "{{" not in user["content"]
