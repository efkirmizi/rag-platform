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


def test_no_heading_content():
    chunks = chunk_markdown("Başlıksız düz metin paragrafı.")
    assert len(chunks) == 1
    assert chunks[0].heading_path == ""


def test_empty_input():
    assert chunk_markdown("") == []
    assert chunk_markdown("## Sadece başlık\n") == []
