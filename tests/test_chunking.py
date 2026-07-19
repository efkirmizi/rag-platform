# -*- coding: utf-8 -*-
from ragplatform.ingestion.chunking import chunk_markdown

SAMPLE = """## Birinci bölüm
İlk paragraf içeriği burada.

İkinci paragraf içeriği burada.

### Alt bölüm
Alt bölüm paragrafı.

## İkinci bölüm
Son paragraf.
"""


def test_heading_path_hierarchy():
    chunks = chunk_markdown(SAMPLE)
    paths = [c.heading_path for c in chunks]
    assert "Birinci bölüm" in paths
    assert "Birinci bölüm > Alt bölüm" in paths
    assert "İkinci bölüm" in paths


def test_max_chars_respected():
    long_text = "## Başlık\n" + "\n\n".join(["kelime " * 60] * 20)
    chunks = chunk_markdown(long_text, max_chars=500)
    assert all(len(c.content) <= 500 for c in chunks)
    assert len(chunks) > 1


def test_oversized_single_paragraph_is_split():
    text = "## Başlık\n" + "a" * 4000
    chunks = chunk_markdown(text, max_chars=1600)
    assert all(len(c.content) <= 1600 for c in chunks)
    assert sum(len(c.content) for c in chunks) >= 3900


def test_oversized_paragraph_never_splits_mid_word():
    """Kelime ortasından kesmek FTS token'ını ve embedding anlamını bozar."""
    words = ["politikası", "çalışan", "izin", "yönetim", "değerlendirme"] * 120
    text = "## Başlık\n" + " ".join(words)
    chunks = chunk_markdown(text, max_chars=200)

    assert len(chunks) > 1
    assert all(len(c.content) <= 200 for c in chunks)
    # Her parça yalnız tam kelimelerden oluşmalı ve sıra korunmalı
    for c in chunks:
        assert all(w in words for w in c.content.split())
    assert " ".join(" ".join(c.content.split()) for c in chunks).split() == words


def test_overlap_shares_text_between_consecutive_chunks():
    paras = ["\n\n".join([f"paragraf {i} " + "dolgu " * 30 for i in range(6)])]
    text = "## Başlık\n" + paras[0]
    without = chunk_markdown(text, max_chars=400, overlap=0)
    with_ov = chunk_markdown(text, max_chars=400, overlap=120)

    assert len(with_ov) >= len(without)
    # ardışık chunk'lar ortak metin paylaşmalı
    shared = [
        bool(set(a.content.split()[-8:]) & set(b.content.split()[:12]))
        for a, b in zip(with_ov, with_ov[1:])
    ]
    assert any(shared), "overlap ile ardışık chunk'lar örtüşmeli"


def test_overlap_respects_max_chars():
    text = "## Başlık\n" + "\n\n".join(["kelime " * 40 for _ in range(8)])
    for c in chunk_markdown(text, max_chars=300, overlap=100):
        assert len(c.content) <= 300


def test_overlap_zero_is_unchanged_default():
    text = "## Başlık\n" + "\n\n".join(["kelime " * 40 for _ in range(5)])
    assert chunk_markdown(text, max_chars=300) == chunk_markdown(text, max_chars=300, overlap=0)


def test_unbreakable_token_still_splits():
    """Boşluksuz dev token (blob/URL) sert kesilir — döngü ilerlemek zorunda."""
    text = "## Başlık\n" + "x" * 900
    chunks = chunk_markdown(text, max_chars=200)
    assert all(len(c.content) <= 200 for c in chunks)
    assert "".join(c.content for c in chunks) == "x" * 900


def test_no_heading_content():
    chunks = chunk_markdown("Başlıksız düz metin paragrafı.")
    assert len(chunks) == 1
    assert chunks[0].heading_path == ""


def test_empty_input():
    assert chunk_markdown("") == []
    assert chunk_markdown("## Sadece başlık\n") == []
