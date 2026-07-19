"""Reranker arayüzü + sağlayıcılar.

Noop (Faz 0 varsayılanı) RRF sırasını korur. CrossEncoderReranker (G-2)
bge-reranker-v2-m3 gibi çok dilli bir cross-encoder ile top-N adayı yeniden
sıralar — hybrid+RRF geniş recall verir, reranker hassasiyeti getirir.
"""

import asyncio
from abc import ABC, abstractmethod

from ragplatform.config import Settings


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]: ...


class NoopReranker(Reranker):
    """RRF sırasını korur — yalnız top_k'ya kırpar. ACL/latency testleri bunu kullanır."""

    name = "noop"

    async def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]:
        return results[:top_k]


class CrossEncoderReranker(Reranker):
    """Cross-encoder ile (query, passage) çiftlerini skorlayıp yeniden sıralar.

    Ağır import (sentence-transformers) lazy: paket, reranker kullanılmadan
    (noop ile) torch'suz çalışabilmeli. `scorer` enjekte edilirse model
    yüklenmez — birim testleri gerçek modeli indirmeden çalışır.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "auto",
        dtype: str = "auto",
        *,
        scorer=None,
    ):
        self.name = model_name
        if scorer is not None:
            self._scorer = scorer
            return
        from sentence_transformers import CrossEncoder

        from ragplatform.hardware import log_device, resolve_device_dtype

        dev, torch_dtype = resolve_device_dtype(device, dtype)
        self._scorer = CrossEncoder(model_name, device=dev)
        # dtype'ı sürümden bağımsız uygula: model.to(dtype) her ST sürümünde çalışır
        # (CrossEncoder ctor'ının model_kwargs desteği sürüme göre değişiyor).
        if torch_dtype is not None:
            self._scorer.model.to(torch_dtype)
        log_device("reranker", model_name, dev, torch_dtype)

    async def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]:
        if not results:
            return []
        pairs = [[query, r["content"]] for r in results]
        scores = await asyncio.to_thread(self._scorer.predict, pairs)
        for r, s in zip(results, scores):
            r["rerank_score"] = float(s)
        ranked = sorted(results, key=lambda r: r["rerank_score"], reverse=True)
        return ranked[:top_k]


def create_reranker(settings: Settings) -> Reranker:
    if settings.reranker_provider == "noop":
        return NoopReranker()
    if settings.reranker_provider == "local":
        return CrossEncoderReranker(
            model_name=settings.reranker_model or "BAAI/bge-reranker-v2-m3",
            device=settings.embeddings_device,
            dtype=settings.embeddings_dtype,
        )
    raise ValueError(f"Bilinmeyen reranker_provider: {settings.reranker_provider}")
