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

from ragplatform.acl.fga import FgaAdmin
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings import create_embeddings
from ragplatform.ingestion.indexer import index_page, upsert_space

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def index_corpus(pool, embedder) -> int:
    """Sentetik sayfaları verilen embedder ile chunk'layıp indexler; chunk sayısını döner.

    FGA'dan bağımsız — yalnız içerik. Matris koşucusu (run_g2_matrix.py) modeli
    değiştirip bunu tekrar çağırarak embedding'leri yeniden yazar (FGA tuple'ları
    değişmez). index_page upsert + chunk replace olduğundan idempotenttir.
    """
    for key, name in corpus.SPACES.items():
        await upsert_space(pool, key, name)
    total_chunks = 0
    for page in corpus.PAGES:
        n = await index_page(
            pool,
            embedder,
            page_key=page["page_key"],
            space_key=page["space"],
            title=page["title"],
            content_md=page["content"],
            url=f"https://confluence.sirket.local/pages/{page['page_key']}",
            is_restricted=page["restricted_to"] is not None,
        )
        total_chunks += n
        flag = " [KISITLI]" if page["restricted_to"] else ""
        print(f"[db] {page['space']:>3} / {page['page_key']:<22} {n} chunk{flag}")
    return total_chunks


def build_tuples() -> list[tuple[str, str, str]]:
    tuples: list[tuple[str, str, str]] = []
    for group, members in corpus.GROUPS.items():
        for user in members:
            tuples.append((f"user:{user}", "member", f"group:{group}"))
    for space, viewer_groups in corpus.SPACE_VIEWERS.items():
        for group in viewer_groups:
            tuples.append((f"group:{group}#member", "viewer", f"space:{space}"))
    for page in corpus.PAGES:
        tuples.append((f"space:{page['space']}", "parent", f"page:{page['page_key']}"))
        if page["restricted_to"]:
            tuples.append(
                (f"group:{page['restricted_to']}#member", "restricted_viewer",
                 f"page:{page['page_key']}")
            )
    return tuples


async def bootstrap_fga(settings) -> tuple[str, str]:
    """OpenFGA store + model + izin tuple'larını yazar; (store_id, model_id) döner.

    State dosyasını (fga_state_file) günceller ki FgaClient.from_settings okusun.
    seed_synthetic.main() ve run_g2_matrix.py paylaşır — tuple'lar tek yerden.
    """
    admin = FgaAdmin(settings.fga_api_url)
    try:
        store_id = await admin.create_store("rag-poc")
        model = json.loads((ROOT / "infra" / "openfga" / "model.json").read_text("utf-8"))
        model_id = await admin.write_model(store_id, model)

        state_file = ROOT / settings.fga_state_file
        state_file.write_text(
            json.dumps({"store_id": store_id, "model_id": model_id}, indent=2),
            encoding="utf-8",
        )
        print(f"[fga] store={store_id} model={model_id} -> {state_file.name}")

        tuples = build_tuples()
        written = await admin.write_tuples(store_id, model_id, tuples)
        print(f"[fga] {written} tuple yazıldı ({len(corpus.PAGES)} sayfa)")
    finally:
        await admin.close()
    return store_id, model_id


async def main() -> None:
    settings = get_settings()

    # --- 1-2) OpenFGA bootstrap + izin tuple'ları ---
    await bootstrap_fga(settings)

    # --- 3) İçerik index'leme ---
    pool = await create_pool(settings.database_url)
    embedder = create_embeddings(settings)
    try:
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
