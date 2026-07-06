# -*- coding: utf-8 -*-
"""G-1 kabul testi (PROJE-PLANI.md Faz 0):

1) SIZINTI = 0: her kullanıcı × sorgu için retrieval çalıştırır; dönen her
   chunk'ın kullanıcının erişim setinde olduğunu, FGA'dan BAĞIMSIZ olarak
   sentetik tanımdan hesaplanan beklenen setle doğrular.
2) LATENCY: p50/p95 retrieval süresi (hedef: p95 < 300ms).

Çıkış kodu: sızıntı varsa 1, yoksa 0.
Çalıştırma: python scripts/acl_leak_test.py
"""

import asyncio
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import synthetic_corpus as corpus

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

# Kasıtlı olarak kısıtlı/yetkisiz içeriği hedefleyen sorgular da var:
QUERIES = [
    "yıllık izin kaç gün",
    "uzaktan çalışma kaç gün ofis",
    "vpn kurulumu TR-4021 hatası",
    "maaş bantları seviye matrisi",
    "işten çıkış erişim iptali",
    "güvenlik açığı bildirimi embargo",
    "masraf beyanı onay limiti",
    "tedarikçi ödeme vadesi iskonto",
    "üretim dağıtım geri alma",
    "bütçe planlama takvimi",
]


async def main() -> int:
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

    violations: list[str] = []
    latencies: list[float] = []
    checked = 0

    try:
        for user in corpus.USERS:
            expected_pages = corpus.expected_allowed_pages(user)
            expected_spaces = corpus.expected_allowed_spaces(user)
            for query in QUERIES:
                resp = await service.retrieve(user, query, top_k=8)
                latencies.append(resp["took_ms"])
                for r in resp["results"]:
                    checked += 1
                    page_key = r["citation"]["page_key"]
                    space_key = r["citation"]["space_key"]
                    if space_key not in expected_spaces:
                        violations.append(
                            f"SIZINTI space: user={user} query='{query}' -> {space_key}/{page_key}"
                        )
                    elif page_key not in expected_pages:
                        violations.append(
                            f"SIZINTI sayfa: user={user} query='{query}' -> {page_key} (kısıtlı)"
                        )

        # Isınmış cache ile latency turu (gerçekçi kullanım: FGA seti cache'te)
        for _ in range(2):
            for user in corpus.USERS[:3]:
                for query in QUERIES[:5]:
                    resp = await service.retrieve(user, query, top_k=8)
                    latencies.append(resp["took_ms"])
    finally:
        await fga.close()
        await embedder.close()
        await pool.close()

    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18]

    print(f"Kontrol edilen sonuç sayısı : {checked}")
    print(f"Kullanıcı × sorgu           : {len(corpus.USERS)} × {len(QUERIES)}")
    print(f"Latency p50 / p95           : {p50:.0f}ms / {p95:.0f}ms  (hedef p95 < 300ms)")

    if violations:
        print(f"\n❌ {len(violations)} SIZINTI BULUNDU:")
        for v in violations:
            print("  " + v)
        return 1

    print("\n✅ ACL sızıntısı: 0 — G-1 sızıntı kriteri sağlandı")
    if p95 >= 300:
        print("⚠️  p95 hedefin üzerinde — HNSW/FTS parametreleri veya cache incelenmeli")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
