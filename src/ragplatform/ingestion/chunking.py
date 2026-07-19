"""Başlık-farkındalıklı basit chunker (Faz 0).

Faz 1'de Docling çıktısı (yapısal parse: tablo, başlık hiyerarşisi) bu modülün
yerini alacak; Chunk arayüzü sabit tutuldu. Overlap bilinçli olarak yok —
eklenecekse eval ile kanıtlanarak eklenir (PROJE-PLANI.md Faz 3).
"""

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chunk:
    heading_path: str
    content: str


def _sections(text: str):
    """Metni başlık hiyerarşisine göre (heading_path, gövde) bölümlerine ayırır."""
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    path = ""
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            if "".join(buf).strip():
                yield path, "\n".join(buf).strip()
            buf = []
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, m.group(2)))
            path = " > ".join(title for _, title in stack)
        else:
            buf.append(line)
    if "".join(buf).strip():
        yield path, "\n".join(buf).strip()


def _flush_oversized(chunks: list["Chunk"], path: str, current: str, max_chars: int) -> str:
    """max_chars'ı aşan metinden bir parça koparıp ekler; kalanı döner.

    Kesim boşlukta yapılır — kelimeyi ortadan bölmek hem FTS token'ını hem
    embedding anlamını bozar ("politikas" gibi yarım kelime hiçbir şeyle
    eşleşmez). Boşluksuz dev bir token varsa (base64 blob, uzun URL) mecburen
    sert kesilir; aksi hâlde döngü ilerlemez.
    """
    window = current[: max_chars + 1]
    cut = max(window.rfind(" "), window.rfind("\n"), window.rfind("\t"))
    if cut <= 0:
        cut = max_chars
    chunks.append(Chunk(path, current[:cut].rstrip()))
    return current[cut:].lstrip()


def _overlap_tail(text: str, overlap: int) -> str:
    """Bir sonraki chunk'ın başına taşınacak kuyruk (kelime sınırında)."""
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    cut = tail.find(" ")
    return tail[cut + 1:] if cut != -1 else tail


def chunk_markdown(text: str, max_chars: int = 1600, overlap: int = 0) -> list[Chunk]:
    """Bölüm içindeki paragrafları max_chars sınırına kadar paketler.

    `overlap`: ardışık chunk'ların paylaştığı karakter sayısı. Sınırın tam
    üstüne düşen bir cevabın ikiye bölünüp hiçbir chunk'ta bütün görünmemesini
    engellemeyi amaçlar. Varsayılan 0 — katkısı ölçülerek kanıtlanmalı
    (bkz. scripts/run_chunking_matrix.py).

    Not: Türkçe'de token/karakter oranı İngilizce'den farklıdır; karakter
    limiti kaba bir vekildir (G-2 ölçümü: bge-m3 ~1.76 token/kelime).
    """
    chunks: list[Chunk] = []
    for path, body in _sections(text):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        current = ""
        for para in paragraphs:
            if current and len(current) + len(para) + 2 > max_chars:
                chunks.append(Chunk(path, current))
                tail = _overlap_tail(current, overlap)
                current = f"{tail}\n\n{para}" if tail else para
            else:
                current = f"{current}\n\n{para}" if current else para
            while len(current) > max_chars:
                current = _flush_oversized(chunks, path, current, max_chars)
        if current:
            chunks.append(Chunk(path, current))
    return chunks
