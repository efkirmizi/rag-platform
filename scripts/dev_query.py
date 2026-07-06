# -*- coding: utf-8 -*-
"""Hızlı deneme CLI'ı.

Örnek: python scripts/dev_query.py ayse "yıllık izin kaç gün"
"""

import argparse
import asyncio
import sys

from ragplatform.acl.access import AccessResolver
from ragplatform.acl.fga import FgaClient
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings import create_embeddings
from ragplatform.retrieval.rerank import NoopReranker
from ragplatform.retrieval.service import RetrievalService

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("user_id")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    pool = await create_pool(settings.database_url)
    fga = FgaClient.from_settings(settings)
    embedder = create_embeddings(settings)
    service = RetrievalService(
        pool=pool,
        embedder=embedder,
        resolver=AccessResolver(fga, ttl_seconds=settings.acl_cache_ttl_seconds),
        reranker=NoopReranker(),
    )
    try:
        resp = await service.retrieve(args.user_id, args.query, args.top_k)
    finally:
        await fga.close()
        await embedder.close()
        await pool.close()

    print(f"kullanıcı={resp['user_id']}  süre={resp['took_ms']}ms  "
          f"erişilebilir space: {resp['allowed_spaces']}")
    if not resp["results"]:
        print("(sonuç yok)")
    for i, r in enumerate(resp["results"], 1):
        c = r["citation"]
        restricted = " [KISITLI]" if r["debug"]["is_restricted"] else ""
        print(f"\n{i}. [{c['space_key']}] {c['title']} — {c['heading_path']}{restricted}")
        print(f"   skor={r['score']:.4f} vec_rank={r['debug']['vec_rank']} "
              f"fts_rank={r['debug']['fts_rank']}")
        preview = r["content"][:180].replace("\n", " ")
        print(f"   {preview}...")


if __name__ == "__main__":
    asyncio.run(main())
