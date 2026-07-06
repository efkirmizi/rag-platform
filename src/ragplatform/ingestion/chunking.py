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


def chunk_markdown(text: str, max_chars: int = 1600) -> list[Chunk]:
    """Bölüm içindeki paragrafları max_chars sınırına kadar paketler.

    Not: Türkçe'de token/karakter oranı İngilizce'den farklıdır; karakter
    limiti kaba bir vekildir. G-2'deki token verimliliği ölçümünden sonra
    limit token bazlıya çevrilebilir.
    """
    chunks: list[Chunk] = []
    for path, body in _sections(text):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        current = ""
        for para in paragraphs:
            if current and len(current) + len(para) + 2 > max_chars:
                chunks.append(Chunk(path, current))
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
            while len(current) > max_chars:
                chunks.append(Chunk(path, current[:max_chars]))
                current = current[max_chars:].lstrip()
        if current:
            chunks.append(Chunk(path, current))
    return chunks
