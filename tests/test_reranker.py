# -*- coding: utf-8 -*-
"""CrossEncoderReranker sıralama mantığı — gerçek model indirmeden.

Skorlayıcı enjekte edilir (`scorer=`): cross-encoder yerine sahte bir
`.predict(pairs)` verilir; böylece sıralama/top_k/skor-yazımı davranışı
GPU ve indirme olmadan test edilir.
"""

import pytest

from ragplatform.config import Settings
from ragplatform.retrieval.rerank import (
    CrossEncoderReranker,
    NoopReranker,
    create_reranker,
)


class FakeScorer:
    """content uzunluğunu skor olarak döndürür — deterministik, tahmin edilebilir sıra."""

    def __init__(self):
        self.calls = 0

    def predict(self, pairs):
        self.calls += 1
        return [float(len(passage)) for _query, passage in pairs]


def _rows(*contents):
    return [{"content": c, "rrf_score": 0.0} for c in contents]


@pytest.mark.asyncio
async def test_reranker_sorts_by_score_desc_and_truncates():
    rr = CrossEncoderReranker(scorer=FakeScorer())
    rows = _rows("kisa", "en uzun icerik burada", "orta uzunluk")
    out = await rr.rerank("soru", rows, top_k=2)
    assert [r["content"] for r in out] == ["en uzun icerik burada", "orta uzunluk"]
    assert len(out) == 2


@pytest.mark.asyncio
async def test_reranker_writes_score_onto_rows():
    rr = CrossEncoderReranker(scorer=FakeScorer())
    [out] = await rr.rerank("soru", _rows("abcd"), top_k=1)
    assert out["rerank_score"] == 4.0


@pytest.mark.asyncio
async def test_reranker_empty_results():
    rr = CrossEncoderReranker(scorer=FakeScorer())
    assert await rr.rerank("soru", [], top_k=5) == []


@pytest.mark.asyncio
async def test_noop_preserves_rrf_order():
    rr = NoopReranker()
    rows = _rows("a", "b", "c")
    out = await rr.rerank("soru", rows, top_k=2)
    assert [r["content"] for r in out] == ["a", "b"]


def test_factory_noop_default():
    assert isinstance(create_reranker(Settings(reranker_provider="noop")), NoopReranker)


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        create_reranker(Settings(reranker_provider="bogus"))
