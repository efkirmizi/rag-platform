# -*- coding: utf-8 -*-
"""Chunking parametrelerini ölçerek karara bağlar (overlap ve boyut).

Overlap ve chunk boyutu Faz 0'da bilinçli olarak "eval ile kanıtlanmadan
eklenmez" diye ertelenmişti. Eval harness'ı artık var; bu script ertelenen
soruyu kapatır: her yapılandırma için korpusu YENİDEN indexler ve golden_v2
üzerinde ölçer.

Embedding modeli sabit tutulur (ADR-3: bge-m3) — değişken yalnız chunking.

Ön koşul: docker compose up -d · pip install -e ".[local]" (GPU otomatik)
Çalıştırma: python scripts/run_chunking_matrix.py
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import score_run
from seed_synthetic import bootstrap_fga, corpus_model

from ragplatform.acl.access import AccessResolver
from ragplatform.acl.fga import FgaClient
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings.local_st import LocalSTEmbeddings
from ragplatform.ingestion.corpus import index_corpus
from ragplatform.retrieval.rerank import NoopReranker
from ragplatform.retrieval.service import RetrievalService

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOLDEN = ROOT / "eval" / "golden" / "golden_v2.jsonl"

# (max_chars, overlap) — mevcut varsayılan (1600, 0) baseline
CONFIGS = [
    (1600, 0),
    (1600, 200),
    (800, 0),
    (800, 150),
    (2400, 0),
    (2400, 300),
]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--model", default="BAAI/bge-m3")
    args = ap.parse_args()

    items = [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    settings = get_settings()
    pool = await create_pool(settings.database_url)
    await bootstrap_fga(settings)
    fga = FgaClient.from_settings(settings)
    resolver = AccessResolver(fga, ttl_seconds=settings.acl_cache_ttl_seconds)

    embedder = LocalSTEmbeddings(
        model_name=args.model,
        dim=settings.embeddings_dim,
        device=settings.embeddings_device,
        dtype=settings.embeddings_dtype,
    )
    corpus = corpus_model()
    rows = []
    try:
        for max_chars, overlap in CONFIGS:
            n_chunks = await index_corpus(
                pool, embedder, corpus, quiet=True, max_chars=max_chars, overlap=overlap
            )
            service = RetrievalService(pool, embedder, resolver, NoopReranker())
            summary = await score_run(
                service,
                items,
                args.top_k,
                golden_name=GOLDEN.name,
                embedding_model=embedder.name,
                reranker_name="noop",
            )
            m = summary["metrics"]
            para = summary["per_category"].get("parafraz", {}).get("hit@5", 0)
            rows.append(
                {
                    "max_chars": max_chars,
                    "overlap": overlap,
                    "chunks": n_chunks,
                    "mrr": m["mrr"],
                    "hit@1": m["hit@1"],
                    "hit@3": m["hit@3"],
                    "hit@5": m["hit@5"],
                    "parafraz@5": para,
                    "acl_violations": m["acl_violations"],
                    "p95_ms": m["latency_p95_ms"],
                }
            )
            print(
                f"  max_chars={max_chars:<5} overlap={overlap:<4} chunks={n_chunks:<4} "
                f"MRR={m['mrr']:.3f} hit@1={m['hit@1']:.3f} hit@5={m['hit@5']:.3f} "
                f"parafraz@5={para:.3f} acl={m['acl_violations']}"
            )
    finally:
        await fga.close()
        await embedder.close()
        await pool.close()

    base = next(r for r in rows if r["max_chars"] == 1600 and r["overlap"] == 0)
    best = max(rows, key=lambda r: (r["mrr"], r["hit@1"]))
    out = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": args.model,
        "golden_file": GOLDEN.name,
        "baseline": {"max_chars": base["max_chars"], "overlap": base["overlap"]},
        "best": {"max_chars": best["max_chars"], "overlap": best["overlap"]},
        "delta_mrr_vs_baseline": round(best["mrr"] - base["mrr"], 4),
        "rows": rows,
    }
    path = ROOT / "eval" / "results" / "chunking-matrix.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Deneyin geçerliliği: parametreler gerçekten devreye girdi mi? ---
    # Tüm yapılandırmalar aynı sayıda chunk ürettiyse metin hiç bölünmemiştir:
    # max_chars sınırı bağlamamış, dolayısıyla overlap de hiç tetiklenmemiştir.
    # Bu durumda "fark yok" sonucu chunking hakkında BİR ŞEY SÖYLEMEZ — deney
    # boştur. Sessizce yanlış karara varmamak için açıkça uyar.
    distinct_counts = {r["chunks"] for r in rows}
    out["conclusive"] = len(distinct_counts) > 1
    if not out["conclusive"]:
        print(
            f"\n⚠️  SONUÇSUZ: tüm yapılandırmalar aynı {rows[0]['chunks']} chunk'ı üretti.\n"
            "   Korpustaki bölümler max_chars sınırının altında kaldığı için metin hiç\n"
            "   bölünmedi; overlap de hiç devreye girmedi. Bu koşu chunking hakkında\n"
            "   kanıt üretmez — parametreleri ölçmek için daha uzun dokümanlar gerekir\n"
            "   (gerçek Confluence sayfaları bu sentetik sayfalardan çok daha uzundur).\n"
            "   Karar G-0 pilot içeriğine ertelenmeli."
        )
        print(f"Sonuç dosyası: {path.relative_to(ROOT)}")
        return 0

    print(
        f"\nBaseline (1600/0) MRR={base['mrr']:.3f} · "
        f"En iyi ({best['max_chars']}/{best['overlap']}) MRR={best['mrr']:.3f} "
        f"(Δ{out['delta_mrr_vs_baseline']:+.3f})"
    )
    if out["delta_mrr_vs_baseline"] <= 0.005:
        print("Sonuç: anlamlı fark yok → mevcut varsayılan korunmalı (overlap eklemeyin).")
    print(f"Sonuç dosyası: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
