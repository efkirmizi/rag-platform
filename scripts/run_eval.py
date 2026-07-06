# -*- coding: utf-8 -*-
"""Golden set eval harness (G-3).

Her golden soru için retrieval çalıştırır, sayfa bazında ölçer:
- hit@k (k=1,3,5,top_k): beklenen sayfalardan en az biri ilk k sonuçta mı?
- MRR: ilk isabetin sırasının tersi (sayfa bazında, chunk değil)
- yetki-siniri: forbidden_page_keys sonuçlarda çıkarsa İHLAL (exit 1)

Çıktı: konsol raporu + eval/results/<zaman>_<model>.json (baseline takibi için).
Çalıştırma: python scripts/run_eval.py [--golden ...] [--top-k 8]
"""

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

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

ROOT = Path(__file__).resolve().parent.parent
HIT_KS = (1, 3, 5)


def page_order(results: list[dict]) -> list[str]:
    """Chunk sonuçlarını sıra koruyarak sayfa listesine indirger."""
    seen: list[str] = []
    for r in results:
        key = r["citation"]["page_key"]
        if key not in seen:
            seen.append(key)
    return seen


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default=str(ROOT / "eval" / "golden" / "golden_v1.jsonl"))
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    items = [
        json.loads(line)
        for line in Path(args.golden).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

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

    per_item: list[dict] = []
    violations: list[str] = []
    try:
        for item in items:
            resp = await service.retrieve(item["user_id"], item["question"], args.top_k)
            pages = page_order(resp["results"])

            expected = item["expected_page_keys"]
            rank = next((i + 1 for i, p in enumerate(pages) if p in expected), None)

            found_forbidden = [p for p in item["forbidden_page_keys"] if p in pages]
            for p in found_forbidden:
                violations.append(f"{item['id']}: user={item['user_id']} yasaklı sayfa döndü: {p}")

            per_item.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "user_id": item["user_id"],
                    "question": item["question"],
                    "expected": expected,
                    "rank": rank,
                    "hits": {str(k): (rank is not None and rank <= k) for k in HIT_KS},
                    "forbidden_violation": found_forbidden,
                    "took_ms": resp["took_ms"],
                    "returned_pages": pages,
                }
            )
    finally:
        await fga.close()
        await embedder.close()
        await pool.close()

    scored = [i for i in per_item if i["expected"]]  # yetki-siniri hariç
    boundary = [i for i in per_item if not i["expected"]]

    def rate(items_: list[dict], k: int) -> float:
        return sum(i["hits"][str(k)] for i in items_) / len(items_) if items_ else 0.0

    mrr = (
        sum(1.0 / i["rank"] for i in scored if i["rank"]) / len(scored) if scored else 0.0
    )

    categories = sorted({i["category"] for i in scored})
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "golden_file": Path(args.golden).name,
        "item_count": len(per_item),
        "embedding_model": embedder.name,
        "reranker": "noop",
        "top_k": args.top_k,
        "metrics": {
            "mrr": round(mrr, 4),
            **{f"hit@{k}": round(rate(scored, k), 4) for k in HIT_KS},
            f"hit@{args.top_k}": round(
                sum(i["rank"] is not None for i in scored) / len(scored), 4
            ) if scored else 0.0,
            "acl_violations": len(violations),
            "latency_p95_ms": round(
                statistics.quantiles([i["took_ms"] for i in per_item], n=20)[18], 1
            ),
        },
        "per_category": {
            cat: {
                "n": len([i for i in scored if i["category"] == cat]),
                **{f"hit@{k}": round(rate([i for i in scored if i["category"] == cat], k), 4)
                   for k in HIT_KS},
            }
            for cat in categories
        },
        "boundary_items": {"n": len(boundary), "violations": violations},
        "items": per_item,
    }

    results_dir = ROOT / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_model = embedder.name.replace("/", "-").replace("\\", "-").replace(":", "-")
    out = results_dir / f"{stamp}_{safe_model}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # --- Konsol raporu ---
    m = summary["metrics"]
    print(f"Golden set : {summary['golden_file']}  ({len(per_item)} soru)")
    print(f"Embedding  : {embedder.name}   reranker: noop   top_k: {args.top_k}")
    print(f"\nMRR        : {m['mrr']:.3f}")
    for k in HIT_KS:
        print(f"hit@{k}      : {m[f'hit@{k}']:.3f}")
    print(f"latency p95: {m['latency_p95_ms']}ms")
    print("\nKategori bazında hit@5:")
    for cat, stats in summary["per_category"].items():
        print(f"  {cat:<16} {stats['hit@5']:.3f}  (n={stats['n']})")
    missed = [i for i in scored if i["rank"] is None]
    if missed:
        print("\nIskalanan sorular (hit@{}=0):".format(args.top_k))
        for i in missed:
            print(f"  [{i['category']}] {i['id']} {i['user_id']}: {i['question']}")
    print(f"\nYetki-sınırı: {len(boundary)} soru, {len(violations)} ihlal")
    if violations:
        for v in violations:
            print("  ❌ " + v)
        print("\n❌ ACL İHLALİ — eval BAŞARISIZ")
        return 1
    print(f"\nSonuç dosyası: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
