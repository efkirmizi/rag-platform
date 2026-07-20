# -*- coding: utf-8 -*-
"""Faz 0 ortamını tek komutla doldurur:

1) OpenFGA store + authorization model oluşturur → infra/openfga/store.state.json
2) Grup üyeliği / space viewer / sayfa kısıt tuple'larını yazar
3) Sentetik sayfaları chunk'layıp embed'leyip Postgres'e indexler

Çalıştırma:  python scripts/seed_synthetic.py
Ön koşul:    docker compose up -d  (postgres + openfga ayakta)

Idempotent değildir: temiz kurulum için `docker compose down -v` sonrası çalıştırın.
(Her çalıştırma yeni bir FGA store oluşturur; eskisi kullanılmaz ama silinmez.)
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import synthetic_corpus as corpus

from ragplatform.acl.bootstrap import bootstrap_store
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings import create_embeddings
from ragplatform.ingestion import corpus as corpus_model_mod
from ragplatform.ingestion.corpus import Corpus, Page

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def corpus_model() -> Corpus:
    """Sentetik senaryo tanımını kaynak-bağımsız Corpus modeline çevirir.

    Böylece seed, klasör connector'ı ile aynı tuple üretimi ve index yolunu
    kullanır (ragplatform.ingestion.corpus).
    """
    return Corpus(
        spaces=dict(corpus.SPACES),
        groups={g: list(m) for g, m in corpus.GROUPS.items()},
        space_viewers={s: list(v) for s, v in corpus.SPACE_VIEWERS.items()},
        pages=[
            Page(
                page_key=p["page_key"],
                space=p["space"],
                title=p["title"],
                content=p["content"],
                restricted_to=p["restricted_to"],
                url=f"https://confluence.sirket.local/pages/{p['page_key']}",
            )
            for p in corpus.PAGES
        ],
    )


async def index_corpus(pool, embedder) -> int:
    """Sentetik sayfaları verilen embedder ile indexler; chunk sayısını döner.

    FGA'dan bağımsız — yalnız içerik. Matris koşucusu (run_g2_matrix.py) modeli
    değiştirip bunu tekrar çağırarak embedding'leri yeniden yazar (FGA tuple'ları
    değişmez); index_page upsert + chunk replace olduğundan idempotenttir.
    """
    return await corpus_model_mod.index_corpus(pool, embedder, corpus_model())


def build_tuples() -> list[tuple[str, str, str]]:
    """Sentetik senaryonun OpenFGA tuple'ları (ortak üretici üzerinden)."""
    return corpus_model_mod.build_tuples(corpus_model())


async def bootstrap_fga(settings) -> tuple[str, str]:
    """OpenFGA store + model + izin tuple'larını yazar; (store_id, model_id) döner."""
    model = json.loads((ROOT / "infra" / "openfga" / "model.json").read_text("utf-8"))
    return await bootstrap_store(settings, model, build_tuples(), store_name="rag-poc")


async def main() -> None:
    settings = get_settings()

    # --- 1-2) OpenFGA bootstrap + izin tuple'ları ---
    await bootstrap_fga(settings)

    # --- 3) İçerik index'leme ---
    pool = await create_pool(settings.database_url)
    embedder = create_embeddings(settings)
    try:
        # Seed, ortamı KURAR — mevcut index'e eklemez. Başka bir korpus (ör.
        # klasör connector'ıyla yüklenen gerçek korpus) index'te kalırsa
        # sızıntı testi onları "beklenmeyen sayfa" olarak raporlar (oracle
        # yalnız sentetik sayfaları bilir) ve gerçek bir ACL hatasıymış gibi
        # görünür. Space anahtarları da çakışabilir.
        await pool.execute("TRUNCATE spaces CASCADE")
        total_chunks = await index_corpus(pool, embedder)
        print(
            f"\nÖzet: {len(corpus.SPACES)} space, {len(corpus.PAGES)} sayfa, "
            f"{total_chunks} chunk (embedding: {embedder.name})"
        )
        print("Sıradaki adım: python scripts/acl_leak_test.py")
    finally:
        await embedder.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
