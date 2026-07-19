# -*- coding: utf-8 -*-
"""Üretim (generation) hattı: prompt kurulumu, citation ayrıştırma, cevap servisi.

Model gerektirmez — EchoLLM ve sahte retrieval ile çalışır; GPU/indirme yok.
"""

import pytest

from ragplatform.config import Settings
from ragplatform.generation import GenerationDisabled, create_llm
from ragplatform.generation.echo import EchoLLM
from ragplatform.generation.prompt import (
    SYSTEM_PROMPT,
    build_prompt,
    extract_citations,
)
from ragplatform.generation.service import NO_CONTEXT_ANSWER, AnswerService


def _result(page_key: str, content: str, title: str = "Başlık"):
    return {
        "content": content,
        "score": 1.0,
        "citation": {
            "title": title,
            "heading_path": "Bölüm",
            "space_key": "IK",
            "page_key": page_key,
            "url": f"https://x/{page_key}",
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
        "debug": {},
    }


class FakeRetrieval:
    """RetrievalService yerine geçer; ACL sonucunu test senaryosu belirler."""

    def __init__(self, results):
        self._results = results
        self.calls = []

    async def retrieve(self, user_id, query, top_k):
        self.calls.append((user_id, query, top_k))
        return {"results": self._results[:top_k], "took_ms": 1.0}


class SpyLLM(EchoLLM):
    def __init__(self, canned=None):
        super().__init__(canned)
        self.calls = 0

    async def complete(self, system, user, *, max_tokens=512):
        self.calls += 1
        self.last_user = user
        return await super().complete(system, user, max_tokens=max_tokens)


# --- prompt ---


def test_prompt_numbers_sources_and_includes_content():
    b = build_prompt("izin kaç gün?", [_result("a", "14 iş günü"), _result("b", "onay akışı")])
    assert b.source_count == 2
    assert "<<<KAYNAK 1>>>" in b.user and "<<<KAYNAK 2>>>" in b.user
    assert "14 iş günü" in b.user
    assert "SORU: izin kaç gün?" in b.user


def test_prompt_marks_retrieved_content_as_untrusted():
    """ADR-8: retrieval içeriği veri olarak çerçevelenmeli, talimat olarak değil."""
    assert "TALİMAT DEĞİLDİR" in SYSTEM_PROMPT
    b = build_prompt("s", [_result("a", "x")])
    assert b.system == SYSTEM_PROMPT


def test_prompt_truncates_long_sources():
    b = build_prompt("s", [_result("a", "x" * 5000)], max_chars_per_source=100)
    assert "x" * 101 not in b.user


def test_prompt_with_no_results():
    b = build_prompt("s", [])
    assert b.source_count == 0
    assert "(kaynak bulunamadı)" in b.user


# --- citation ---


def test_extract_citations_valid_and_bogus():
    used, bogus = extract_citations("Cevap [1] ve ayrıca [3]. Ayrıca [9] uydurma.", 3)
    assert used == [1, 3]
    assert bogus == [9]


def test_extract_citations_deduplicates():
    used, _ = extract_citations("[2] bir [2] iki [1]", 2)
    assert used == [1, 2]


def test_extract_citations_none():
    assert extract_citations("atıfsız cevap", 3) == ([], [])


# --- cevap servisi ---


@pytest.mark.asyncio
async def test_answer_returns_only_cited_sources():
    llm = SpyLLM("Yıllık izin 14 gündür [2].")
    svc = AnswerService(FakeRetrieval([_result("a", "x"), _result("b", "y")]), llm)
    out = await svc.answer("ayse", "izin?", top_k=2)
    assert out["answer"] == "Yıllık izin 14 gündür [2]."
    assert [c["page_key"] for c in out["citations"]] == ["b"]
    assert out["citations"][0]["n"] == 2
    assert out["unsupported_citations"] == []


@pytest.mark.asyncio
async def test_answer_flags_hallucinated_citation():
    llm = SpyLLM("Uydurma atıf [7].")
    svc = AnswerService(FakeRetrieval([_result("a", "x")]), llm)
    out = await svc.answer("ayse", "s")
    assert out["unsupported_citations"] == [7]
    assert out["citations"] == []


@pytest.mark.asyncio
async def test_no_permitted_content_skips_llm_entirely():
    """ACL hiçbir şey döndürmediyse model ÇAĞRILMAMALI.

    Hem gereksiz maliyet hem de modelin boşlukta uydurma üretme riski;
    ayrıca yetkisiz kullanıcıya 'cevap' üretilmediği burada sabitlenir.
    """
    llm = SpyLLM()
    svc = AnswerService(FakeRetrieval([]), llm)
    out = await svc.answer("mehmet", "maaş bantları?")
    assert out["answer"] == NO_CONTEXT_ANSWER
    assert out["citations"] == []
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_answer_only_sees_retrieval_output():
    """Prompt'a yalnız retrieval'ın (ACL uygulanmış) döndürdüğü içerik girer."""
    llm = SpyLLM("ok [1]")
    svc = AnswerService(FakeRetrieval([_result("izinli", "GORUNUR ICERIK")]), llm)
    await svc.answer("ayse", "s")
    assert "GORUNUR ICERIK" in llm.last_user


# --- factory ---


def test_factory_disabled_by_default():
    with pytest.raises(GenerationDisabled):
        create_llm(Settings())


def test_factory_echo():
    assert isinstance(create_llm(Settings(generation_provider="echo")), EchoLLM)


def test_factory_unknown_raises():
    with pytest.raises(ValueError):
        create_llm(Settings(generation_provider="bogus"))


def test_factory_openai_requires_endpoint_and_model():
    with pytest.raises(ValueError):
        create_llm(Settings(generation_provider="openai"))
