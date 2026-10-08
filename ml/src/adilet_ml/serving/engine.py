"""Model/runtime abstraction used by the FastAPI service."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from adilet_ml.retrieval.sparse import SparseEncoder, lexical_overlap_score, tokenize
from adilet_ml.schemas import (
    GenerateDone,
    GenerateRequest,
    GenerateUsage,
    Manifest,
    RerankScore,
    SparseVector,
)

MAX_TEXT_CHARS = 8000
DEFAULT_MANIFEST = Path(__file__).resolve().parents[3] / "models" / "model_manifest.json"


class EngineLoadError(RuntimeError):
    pass


def load_manifest(path: Path | None = None) -> Manifest:
    manifest_path = Path(os.getenv("MODEL_MANIFEST_PATH", str(path or DEFAULT_MANIFEST)))
    if not manifest_path.exists():
        raise EngineLoadError(f"model manifest not found: {manifest_path}")
    return Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=100_000)
def _token_vector(token: str, dim: int) -> np.ndarray:
    seed = int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "little")
    return np.random.default_rng(seed).standard_normal(dim).astype(np.float32)


class HashEmbedder:
    """Deterministic local embedder for offline integration and tests."""

    def __init__(self, dim: int, max_seq_len: int = 512) -> None:
        self.dim = dim
        self.max_seq_len = max_seq_len

    def encode(self, texts: list[str], prefixes: list[str]) -> tuple[list[list[float]], list[bool]]:
        dense: list[list[float]] = []
        truncated: list[bool] = []
        for text, prefix in zip(texts, prefixes, strict=True):
            tokens = tokenize(prefix + text)
            truncated.append(len(tokens) > self.max_seq_len)
            tokens = tokens[: self.max_seq_len]
            vec = np.zeros(self.dim, dtype=np.float32)
            for token in tokens:
                vec += _token_vector(token, self.dim)
            norm = float(np.linalg.norm(vec))
            if norm == 0.0:
                vec[0] = 1.0
                norm = 1.0
            dense.append((vec / norm).tolist())
        return dense, truncated


class SentenceTransformerEmbedder:
    """Optional real embedder backend, activated by env when dependencies are installed."""

    def __init__(self, model_name: str, dim: int, max_seq_len: int = 512) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EngineLoadError(
                "sentence-transformers is not installed; install adilet-ml[models]"
            ) from exc
        self.model = SentenceTransformer(model_name, cache_folder=os.getenv("MODEL_CACHE_DIR"))
        self.dim = dim
        self.max_seq_len = max_seq_len

    def encode(self, texts: list[str], prefixes: list[str]) -> tuple[list[list[float]], list[bool]]:
        prepared = [prefix + text for text, prefix in zip(texts, prefixes, strict=True)]
        truncated = [len(tokenize(text)) > self.max_seq_len for text in prepared]
        vectors = self.model.encode(
            prepared,
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=int(os.getenv("ADILET_ML_BATCH_SIZE", "32")),
            show_progress_bar=False,
        )
        return vectors.astype(np.float32).tolist(), truncated


def _build_embedder(manifest: Manifest) -> HashEmbedder | SentenceTransformerEmbedder:
    backend = os.getenv("ADILET_ML_EMBEDDER_BACKEND", "hash").lower()
    max_seq_len = manifest.embedder.max_seq_len or 512
    if backend in {"sentence-transformers", "st"}:
        model_name = manifest.embedder.hf_repo or manifest.embedder.id
        return SentenceTransformerEmbedder(model_name, manifest.embedder.dim, max_seq_len)
    return HashEmbedder(manifest.embedder.dim, max_seq_len)


class MlEngine:
    def __init__(self, manifest: Manifest) -> None:
        self.manifest = manifest
        self.embedder = _build_embedder(manifest)
        sparse_params = manifest.sparse.params
        self.sparse = SparseEncoder(
            k1=float(sparse_params.get("k1", 1.2)),
            b=float(sparse_params.get("b", 0.75)),
            avgdl=float(sparse_params.get("avgdl", 142.3)),
        )
        self.llm_base_url = os.getenv("LLM_BASE_URL")
        self.llm_model = os.getenv("LLM_MODEL")
        self.llm_api_key = os.getenv("LLM_API_KEY")

    @property
    def pipeline_version(self) -> str:
        return self.manifest.pipeline_version

    def embed(
        self,
        texts: list[str],
        kind: str,
        *,
        return_dense: bool,
        return_sparse: bool,
    ) -> tuple[list[list[float]] | None, list[SparseVector] | None, list[bool]]:
        if any(len(text) > MAX_TEXT_CHARS for text in texts):
            raise ValueError(f"each text must be at most {MAX_TEXT_CHARS} chars")
        prefix = (
            self.manifest.embedder.query_prefix
            if kind == "query"
            else self.manifest.embedder.passage_prefix
        )
        prefixes = [prefix] * len(texts)
        dense: list[list[float]] | None = None
        truncated = [False] * len(texts)
        if return_dense:
            dense, truncated = self.embedder.encode(texts, prefixes)
        sparse = None
        if return_sparse:
            sparse = [
                self.sparse.encode_query(text, _detect_lang(text))
                if kind == "query"
                else self.sparse.encode_passage(text, _detect_lang(text))
                for text in texts
            ]
        return dense, sparse, truncated

    def rerank(
        self, query: str, candidates: list[tuple[str, str]], top_n: int | None
    ) -> list[RerankScore]:
        scored = [
            RerankScore(id=cid, score=lexical_overlap_score(query, text))
            for cid, text in candidates
        ]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored if top_n is None else scored[:top_n]

    def fallback_answer(self, body: GenerateRequest) -> str:
        if not body.sources:
            return refusal_text(body.lang)
        first = body.sources[0]
        sentence = _first_sentence(first.text) or first.title
        if body.lang == "kk":
            return f"Берілген дереккөздерге сүйенсек: {sentence} [{first.ref}]"
        return f"Согласно предоставленным источникам: {sentence} [{first.ref}]"

    async def generate_stream(
        self, body: GenerateRequest
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        if os.getenv("ADILET_ML_GENERATOR_MODE", "fallback") == "openai":
            async for event in self._openai_stream(body):
                yield event
            return
        started = time.perf_counter()
        text = self.fallback_answer(body)
        pieces = re.findall(r"\S+\s*", text)
        ttft_ms: int | None = None
        for piece in pieces:
            if ttft_ms is None:
                ttft_ms = int((time.perf_counter() - started) * 1000)
            yield "token", {"text": piece}
        done = GenerateDone(
            text=text,
            finish_reason="stop",
            usage=GenerateUsage(
                prompt_tokens=sum(len(s.text.split()) for s in body.sources),
                completion_tokens=len(pieces),
            ),
            ttft_ms=ttft_ms,
            total_ms=int((time.perf_counter() - started) * 1000),
            model_version=self.pipeline_version,
        )
        yield "done", done.model_dump()

    async def generate_once(self, body: GenerateRequest) -> GenerateDone:
        if os.getenv("ADILET_ML_GENERATOR_MODE", "fallback") == "openai":
            text = ""
            done_payload: dict[str, Any] | None = None
            async for event, payload in self._openai_stream(body):
                if event == "token":
                    text += str(payload.get("text", ""))
                elif event == "done":
                    done_payload = payload
            if done_payload is not None:
                return GenerateDone.model_validate(done_payload)
            return GenerateDone(
                text=text, finish_reason="stop", model_version=self.pipeline_version
            )
        started = time.perf_counter()
        text = self.fallback_answer(body)
        return GenerateDone(
            text=text,
            finish_reason="stop",
            usage=GenerateUsage(
                prompt_tokens=sum(len(s.text.split()) for s in body.sources),
                completion_tokens=len(text.split()),
            ),
            ttft_ms=0,
            total_ms=int((time.perf_counter() - started) * 1000),
            model_version=self.pipeline_version,
        )

    async def _openai_stream(
        self, body: GenerateRequest
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        if not self.llm_base_url or not self.llm_model:
            yield "error", {"code": "llm_unavailable", "message": "LLM endpoint is not configured"}
            return
        prompt = build_prompt(body)
        headers = {"Authorization": f"Bearer {self.llm_api_key}"} if self.llm_api_key else {}
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": body.temperature,
            "max_tokens": body.max_tokens,
            "stream": True,
        }
        started = time.perf_counter()
        text = ""
        ttft_ms: int | None = None
        try:
            timeout = httpx.Timeout(120.0)
            async with (
                httpx.AsyncClient(timeout=timeout, headers=headers) as client,
                client.stream(
                    "POST",
                    f"{self.llm_base_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {}).get("content", "")
                    if not delta:
                        continue
                    if ttft_ms is None:
                        ttft_ms = int((time.perf_counter() - started) * 1000)
                    text += delta
                    yield "token", {"text": delta}
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            yield "error", {"code": "llm_unavailable", "message": str(exc)}
            return
        done = GenerateDone(
            text=text,
            finish_reason="stop",
            usage=GenerateUsage(prompt_tokens=None, completion_tokens=None),
            ttft_ms=ttft_ms,
            total_ms=int((time.perf_counter() - started) * 1000),
            model_version=self.pipeline_version,
        )
        yield "done", done.model_dump()


def _detect_lang(text: str) -> str:
    kk_chars = set("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
    return "kk" if any(char in kk_chars for char in text) else "ru"


def _first_sentence(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    match = re.search(r"(.{20,240}?[.!?])\s", compact + " ")
    return match.group(1) if match else compact[:240]


def refusal_text(lang: str) -> str:
    if lang == "kk":
        return "Берілген дереккөздерде жауап жоқ."
    return "В предоставленных источниках нет ответа."


def build_prompt(body: GenerateRequest) -> str:
    sources = "\n\n".join(
        f"[{source.ref}] {source.title}\n{source.text}" for source in body.sources
    )
    lang_name = "Kazakh" if body.lang == "kk" else "Russian"
    return (
        "Answer only from the numbered sources. Cite every factual claim with [n]. "
        "If the sources do not answer, say that plainly. Do not give personal legal advice.\n\n"
        f"Language: {lang_name}\nQuestion: {body.question}\n\nSources:\n{sources}"
    )
