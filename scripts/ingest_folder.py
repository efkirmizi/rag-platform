# -*- coding: utf-8 -*-
"""Kendi dokümanlarını indexle (bring-your-own-docs).

Bir klasördeki front-matter'lı markdown dosyalarını + permissions.json izin
yapısını okur, OpenFGA'ya izinleri yazar ve içeriği Postgres'e indexler.
Sonrasında sentetik korpusla aynı ACL'li retrieval hattı geçerlidir.

Çalıştırma:
  python scripts/ingest_folder.py --docs ./examples/docs
  python scripts/ingest_folder.py --docs ./mydocs --check   # yalnız doğrula

Ön koşul: docker compose up -d  (postgres + openfga ayakta)
Format ve örnek: examples/docs/ · README

Not: her çalıştırma YENİ bir OpenFGA store oluşturur ve state dosyasını
günceller — yani bu klasör aktif korpus olur. İçerik tarafında index_page
upsert olduğundan aynı page_key'ler güncellenir.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ragplatform.acl.bootstrap import bootstrap_store
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings import create_embeddings
from ragplatform.ingestion.corpus import build_tuples, index_corpus
from ragplatform.ingestion.folder_source import FolderSourceError, load_folder

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Klasördeki markdown'ları ACL'li olarak indexle")
    parser.add_argument("--docs", required=True, help="permissions.json + *.md içeren klasör")
    parser.add_argument("--check", action="store_true", help="Yalnız doğrula, hiçbir şey yazma")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Index'i temizle: yalnız bu klasör kalsın (önceki korpus silinir)",
    )
    args = parser.parse_args()

    try:
        corpus = load_folder(args.docs)
    except FolderSourceError as e:
        print(f"❌ {e}")
        return 1

    errors = corpus.validate()
    if errors:
        print(f"❌ Korpus doğrulaması başarısız ({len(errors)} sorun):")
        for e in errors:
            print("   -", e)
        return 1

    restricted = [p for p in corpus.pages if p.is_restricted]
    print(
        f"✅ Doğrulandı: {len(corpus.spaces)} space, {len(corpus.pages)} sayfa "
        f"({len(restricted)} kısıtlı), {len(corpus.groups)} grup, "
        f"{len(corpus.users())} kullanıcı"
    )
    for user in sorted(corpus.users()):
        print(
            f"   {user:<12} space: {sorted(corpus.allowed_spaces(user))} "
            f"({len(corpus.allowed_pages(user))} sayfa)"
        )
    if args.check:
        return 0

    settings = get_settings()
    model = json.loads((ROOT / "infra" / "openfga" / "model.json").read_text("utf-8"))
    await bootstrap_store(settings, model, build_tuples(corpus), store_name="rag-folder")

    pool = await create_pool(settings.database_url)
    embedder = create_embeddings(settings)
    try:
        if args.reset:
            # spaces -> pages -> chunks zinciri CASCADE ile temizlenir. Aksi hâlde
            # önceki korpus (ör. sentetik seed) index'te kalır ve sonuçlara karışır;
            # space anahtarları da çakışabilir.
            await pool.execute("TRUNCATE spaces CASCADE")
            print("[db] mevcut index temizlendi (--reset)")
        total = await index_corpus(pool, embedder, corpus)
        print(f"\nÖzet: {len(corpus.pages)} sayfa, {total} chunk (embedding: {embedder.name})")
        first_user = sorted(corpus.users())[0] if corpus.users() else "<kullanıcı>"
        print(f'Deneyin: python scripts/dev_query.py {first_user} "<sorunuz>"')
    finally:
        await embedder.close()
        await pool.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
