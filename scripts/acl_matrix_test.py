# -*- coding: utf-8 -*-
"""Tüketici ACL testi: HER kullanıcı × HER doküman çifti ayrı ayrı yoklanır.

Mevcut `acl_leak_test.py` 10 elle seçilmiş sorguyu 6 kullanıcıyla koşuyor.
İyi ama iki açığı var:

1. **Kapsam.** Kısıtlı bir dokümanı hiçbir sorgu güçlü biçimde hedeflemiyorsa,
   o doküman sızsa bile test görmez. Burada her doküman için sorgu O DOKÜMANIN
   KENDİ METNİNDEN üretilir — yani her belge, onu bulmaya en yatkın sorguyla
   ve her kullanıcı gözüyle bilerek yoklanır.

2. **Tek yön.** Eski test yalnız "yetkisiz içerik dönmesin"i kontrol ediyor.
   Oysa ADR-4'ün pre-filter tercihinin gerekçesi post-filter'ın **dar yetkili
   kullanıcıya boş sonuç vermesi**ydi — yani AŞIRI FİLTRELEME de bir hatadır ve
   hiç test edilmiyordu. Bu script iki yönü de doğrular:

       sızıntı        : yetkisiz kullanıcı dokümanı ALMAMALI
       erişilebilirlik: yetkili kullanıcı, dokümanın kendi metninden türeyen
                        sorguyla o dokümanı ALABİLMELİ

Doğruluk kaynağı Corpus.allowed_pages() — FGA/SQL'den bağımsız hesap; iki taraf
aynı yerden beslenmediği için modelleme hataları da yakalanır.

Çalıştırma:
  python scripts/acl_matrix_test.py                       # sentetik korpus
  python scripts/acl_matrix_test.py --docs data/tr-corpus  # klasör korpusu
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_synthetic import corpus_model

from ragplatform.acl.access import AccessResolver
from ragplatform.acl.bootstrap import bootstrap_store
from ragplatform.acl.fga import FgaClient
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings import create_embeddings
from ragplatform.ingestion.corpus import Corpus, Page, build_tuples, index_corpus
from ragplatform.ingestion.folder_source import load_folder
from ragplatform.retrieval.rerank import NoopReranker
from ragplatform.retrieval.service import RetrievalService

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_WORD = re.compile(r"[\wçğıöşüÇĞİÖŞÜ]+", re.UNICODE)


def probe_query(page: Page, max_words: int = 12) -> str:
    """Dokümanı bulmaya en yatkın sorguyu dokümanın KENDİ metninden üretir.

    Başlık + gövdeden ilk anlamlı kelimeler. Amaç 'gerçekçi sorgu' değil,
    **maksimum baskı**: bu sorgu bile yetkisiz kullanıcıya belgeyi
    getirmiyorsa filtre gerçekten sızdırmıyor demektir.
    """
    body = re.sub(r"^#+ .*$", " ", page.content, flags=re.M)  # başlık satırlarını at
    words = _WORD.findall(body)
    tail = " ".join(w for w in words if len(w) > 3)[:200]
    return f"{page.title} {tail}".strip()[:300]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=None, help="Klasör korpusu; yoksa sentetik")
    ap.add_argument(
        "--top-k",
        type=int,
        default=50,
        help="Geniş tutulur: sıralama gürültüsü yüzünden sahte 'erişilemez' çıkmasın",
    )
    ap.add_argument("--reindex", action="store_true", help="Korpusu yeniden indexle")
    args = ap.parse_args()

    corpus: Corpus = load_folder(args.docs) if args.docs else corpus_model()
    if errs := corpus.validate():
        print(f"❌ Korpus geçersiz: {errs[:3]}")
        return 1

    settings = get_settings()
    pool = await create_pool(settings.database_url)
    embedder = create_embeddings(settings)
    fga_model = json.loads((ROOT / "infra" / "openfga" / "model.json").read_text("utf-8"))
    await bootstrap_store(settings, fga_model, build_tuples(corpus), store_name="rag-aclmatrix", quiet=True)
    fga = FgaClient.from_settings(settings)
    service = RetrievalService(
        pool,
        embedder,
        AccessResolver(fga, ttl_seconds=settings.acl_cache_ttl_seconds),
        NoopReranker(),
        candidate_k=200,
        fused_k=args.top_k,
    )

    users = sorted(corpus.users())
    leaks: list[str] = []
    unreachable: list[str] = []
    checked = 0

    try:
        if args.reindex:
            await pool.execute("TRUNCATE spaces CASCADE")
            await index_corpus(pool, embedder, corpus, quiet=True)

        for page in corpus.pages:
            query = probe_query(page)
            for user in users:
                resp = await service.retrieve(user, query, args.top_k)
                returned = {r["citation"]["page_key"] for r in resp["results"]}
                permitted = page.page_key in corpus.allowed_pages(user)
                got = page.page_key in returned
                checked += 1

                if got and not permitted:
                    leaks.append(f"SIZINTI  {user} → {page.page_key} (yetkisiz)")
                elif permitted and not got:
                    unreachable.append(
                        f"ERİŞİLEMEZ  {user} → {page.page_key} "
                        f"(yetkili ama kendi metninden türeyen sorguyla top-{args.top_k}'te yok)"
                    )
    finally:
        await fga.close()
        await embedder.close()
        await pool.close()

    restricted = sum(1 for p in corpus.pages if p.is_restricted)
    print(f"Korpus        : {len(corpus.pages)} doküman ({restricted} kısıtlı), {len(users)} kullanıcı")
    print(f"Yoklanan çift : {checked}  (her doküman × her kullanıcı, top-{args.top_k})")
    print(f"Sızıntı       : {len(leaks)}")
    print(f"Erişilemez    : {len(unreachable)}")

    for label, rows in (("SIZINTI", leaks), ("ERİŞİLEMEZ", unreachable)):
        if rows:
            print(f"\n❌ {label}:")
            for r in rows[:25]:
                print("   " + r)
            if len(rows) > 25:
                print(f"   … +{len(rows) - 25} tane daha")

    if leaks or unreachable:
        print("\n❌ ACL matris testi BAŞARISIZ")
        return 1
    print("\n✅ Her kullanıcı × doküman çifti doğru: sızıntı yok, aşırı filtreleme yok")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
