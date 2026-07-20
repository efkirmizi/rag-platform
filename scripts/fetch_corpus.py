# -*- coding: utf-8 -*-
"""Gerçek Türkçe içerikten değerlendirme korpusu indirir.

NEDEN: sentetik korpustaki sayfalar ~300 karakter uzunluğundaydı. Bu yüzden
chunking parametreleri hiç devreye girmedi (chunking matrisi "sonuçsuz" çıktı)
ve ADR-3 embedding kararı sentetik metne dayandı. Ölçümlerin anlamlı olması için
uzun, başlıklı, gerçek Türkçe metin gerekiyor.

İçerik Türkçe Vikipedi'den alınır (CC BY-SA 4.0) ve klasör connector'ının
beklediği düzende yazılır — yani indirilen korpus doğrudan indexlenebilir.

**İçerik repoya konmaz**, yalnız manifest (eval/corpus/*.json) commit'lenir:
boyut ve lisans nedeniyle. Çıktı klasörüne ATTRIBUTION.md yazılır.

**İzinler sentetiktir ve öyle kalmalı:** içerik gerçek, ACL yapısı kurgusal.
Test edilen şey ACL mekanizmasının doğruluğu; onun kontrollü olması gerekir.

Çalıştırma:
  python scripts/fetch_corpus.py
  python scripts/fetch_corpus.py --manifest eval/corpus/tr-wikipedia.json --out data/tr-corpus
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://tr.wikipedia.org/w/api.php"
UA = "rag-platform-corpus/0.1 (personal project; https://github.com/efkirmizi/rag-platform)"


def _slug(title: str) -> str:
    tr = str.maketrans("çğıöşüâîûÇĞİÖŞÜÂÎÛ", "cgiosuaiucgiosuaiu")
    s = title.translate(tr).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def wiki_to_markdown(text: str) -> str:
    """Vikipedi'nin `== Başlık ==` biçimini markdown başlıklarına çevirir.

    Chunker başlık hiyerarşisine göre bölüyor ve heading_path'i citation'a
    koyuyor; bu dönüşüm o yapıyı korur.
    """
    out = []
    for line in text.splitlines():
        m = re.match(r"^(={2,6})\s*(.+?)\s*\1$", line.strip())
        if m:
            level = len(m.group(1)) - 1  # == X == -> h1 sayılmasın, ## olsun
            out.append("#" * max(2, level) + " " + m.group(2))
        else:
            out.append(line)
    return "\n".join(out)


def fetch_extract(title: str, timeout: float = 45.0) -> str:
    """Bir makalenin tam metnini düz metin + bölüm başlıklarıyla getirir.

    Not: `exlimit` yalnız `exintro` ile birlikte çalışır; TAM metin için istek
    başına tek sayfa alınabiliyor — bu yüzden döngüde tek tek çekiyoruz.
    """
    q = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "extracts",
            "explaintext": 1,
            "exsectionformat": "wiki",
            "format": "json",
            "formatversion": 2,
            "redirects": 1,
            "titles": title,
        }
    )
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return ""
    return pages[0].get("extract", "") or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "eval" / "corpus" / "tr-wikipedia.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "tr-corpus"))
    ap.add_argument("--min-chars", type=int, default=2000,
                    help="Bu uzunluğun altındaki makaleler atlanır (kısa metin chunking'i ölçemez)")
    ap.add_argument("--delay", type=float, default=1.0, help="İstekler arası bekleme (nazik olun)")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    written, skipped, total_chars = [], [], 0
    for i, doc in enumerate(manifest["documents"], 1):
        title = doc["title"]
        try:
            text = fetch_extract(title)
        except Exception as e:
            print(f"  [{i:>2}] HATA  {title}: {e}")
            skipped.append((title, str(e)[:60]))
            continue

        if len(text) < args.min_chars:
            reason = "bulunamadı" if not text else f"çok kısa ({len(text)} < {args.min_chars})"
            print(f"  [{i:>2}] atla  {title} — {reason}")
            skipped.append((title, reason))
            time.sleep(args.delay)
            continue

        body = wiki_to_markdown(text)
        space = doc["space"]
        rel = Path(space.lower()) / f"{_slug(title)}.md"
        front = [f"space: {space}", f"title: {title}"]
        if doc.get("restricted_to"):
            front.append(f"restricted_to: {doc['restricted_to']}")
        front.append(f"url: https://tr.wikipedia.org/wiki/{urllib.parse.quote(title)}")

        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + "\n".join(front) + "\n---\n\n" + body, encoding="utf-8")
        written.append((title, len(body), body.count("\n##")))
        total_chars += len(body)
        print(f"  [{i:>2}] ok    {rel}  ({len(body):,} krk, {body.count(chr(10)+'##')} bölüm)")
        time.sleep(args.delay)

    # Klasör connector'ının beklediği izin dosyası
    (out / "permissions.json").write_text(
        json.dumps(
            {
                "spaces": manifest["spaces"],
                "groups": manifest["groups"],
                "space_viewers": manifest["space_viewers"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out / "ATTRIBUTION.md").write_text(
        "# Kaynak ve lisans\n\n"
        "Bu klasördeki metinler **Türkçe Vikipedi**'den alınmıştır ve\n"
        "**CC BY-SA 4.0** ile lisanslıdır (https://creativecommons.org/licenses/by-sa/4.0/).\n"
        "Her dosyanın front-matter'ındaki `url` alanı kaynağı gösterir.\n\n"
        "İçerik bu depoya dahil DEĞİLDİR; `scripts/fetch_corpus.py` ile indirilir.\n"
        "Dosyalardaki space/grup/kısıt bilgileri **sentetiktir** — ACL mekanizmasını\n"
        "test etmek için uydurulmuştur, Vikipedi ile ilgisi yoktur.\n",
        encoding="utf-8",
    )

    avg = total_chars // len(written) if written else 0
    print(
        f"\n{len(written)} doküman yazıldı ({total_chars:,} karakter, ortalama {avg:,}), "
        f"{len(skipped)} atlandı → {out}"
    )
    if written:
        print(f"En uzun: {max(w[1] for w in written):,} krk · en kısa: {min(w[1] for w in written):,} krk")
    print(f'Sıradaki: python scripts/ingest_folder.py --docs "{out}" --reset')
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
