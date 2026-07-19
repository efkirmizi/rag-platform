# -*- coding: utf-8 -*-
"""ACL-filtreli ANN'in ölçekte davranışı (ADR-2 / ADR-4 doğrulaması).

NEDEN: G-1 latency'si 106 chunk'ta ölçüldü — o boyutta planlayıcı HNSW index'ini
hiç kullanmıyor, seq scan yapıyor. Yani projenin tüm latency sayıları "index
kullanılmayan" sayılar ve ADR-2'nin çıkış eşiği ("p95 filtreli ANN > 150ms")
hiç koşmamış bir kod yoluna ait.

Asıl risk şu: HNSW yaklaşık aramadır ve WHERE filtresi index taramasından SONRA
uygulanır. Dar yetkili bir kullanıcıda (kullanıcı korpusun %1'ini görüyor) index
ilk ef_search adayı döndürür, filtre çoğunu eler → hem k sonuç dolmaz hem recall
çöker. pgvector 0.8 bunun için `hnsw.iterative_scan` getirdi (varsayılan: off).

Bu script sentetik ama yapılı (kümelenmiş) veriyle şunu ölçer:
  - recall@k  : ANN sonucunun tam (brute-force) sonuca oranı
  - dolum     : k sonuç gerçekten dönüyor mu (shortfall)
  - p95       : gecikme
  - index kullanıldı mı (EXPLAIN)
üç modda: index yok (exact) · iterative_scan=off · iterative_scan=relaxed_order
ve farklı yetki genişliklerinde (kullanıcı space'lerin %100 / %10 / %1'ini görür).

Ayrı bir `scale` şemasında çalışır — gerçek korpusa dokunmaz.

⚠️ UYARI: Bu script veritabanını ciddi şekilde yükler (yüz binlerce satır + HNSW
index kurulumu). Yetersiz `maintenance_work_mem` ile Postgres backend'i ÇÖKEBİLİR
(tüm veritabanı recovery'ye girer — diğer bağlantılar da düşer). Paylaşılan bir
Postgres'te değil, yerel/atılabilir bir örnekte çalıştırın.

Çalıştırma:
  python scripts/scale_test.py --rows 100000 --spaces 200
  python scripts/scale_test.py --rows 500000 --keep      # şemayı bırak
"""

import argparse
import asyncio
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ragplatform.config import get_settings
from ragplatform.db import create_pool

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIM = 1024


def _vec_literal(values) -> str:
    return "[" + ",".join(f"{v:.5f}" for v in values) + "]"


def _rand_unit(rng: random.Random):
    v = [rng.gauss(0, 1) for _ in range(DIM)]
    n = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / n for x in v]


def _perturb(center: list[float], noise: float, rng: random.Random) -> list[float]:
    spread = noise * (3.0 / DIM) ** 0.5
    return [c + (rng.random() - 0.5) * 2 * spread for c in center]


async def setup(conn, clusters: int, rng: random.Random) -> list[list[float]]:
    await conn.execute("DROP SCHEMA IF EXISTS scale CASCADE")
    await conn.execute("CREATE SCHEMA scale")
    await conn.execute("""
        CREATE TABLE scale.pages (
            id bigserial PRIMARY KEY,
            space_key text NOT NULL,
            is_restricted boolean NOT NULL DEFAULT false
        )""")
    await conn.execute("CREATE INDEX ON scale.pages (space_key)")
    await conn.execute(f"""
        CREATE TABLE scale.chunks (
            id bigserial PRIMARY KEY,
            page_id bigint NOT NULL REFERENCES scale.pages(id),
            embedding vector({DIM})
        )""")
    # Küme merkezleri: gerçek embedding'ler konuya göre kümelenir; düzgün
    # rastgele vektörler ANN için gerçekçi olmayan (aşırı zor) bir uzay verir.
    await conn.execute(f"CREATE TABLE scale.centers (id int PRIMARY KEY, v vector({DIM}))")
    centers = [_rand_unit(rng) for _ in range(clusters)]
    await conn.executemany(
        "INSERT INTO scale.centers(id, v) VALUES($1, $2::vector)",
        [(i, _vec_literal(c)) for i, c in enumerate(centers)],
    )
    return centers


async def generate(conn, rows: int, spaces: int, clusters: int, noise: float) -> float:
    """Sayfaları ve kümelenmiş vektörleri sunucu tarafında üretir (transfer maliyeti yok).

    `noise` = gürültü vektörünün NORMU (merkezler birim vektör). Boyut başına
    düzgün dağılımda ±a için norm ≈ a·sqrt(DIM/3) olduğundan a = noise·sqrt(3/DIM).
    Bu ölçekleme şart: boyut başına sabit bir aralık verilirse 1024 boyutta
    gürültünün normu merkezi ezer ve veri kümesiz (yapısız) hale gelir — ANN
    recall'ı gerçekte olduğundan kötü görünür.
    """
    spread = noise * (3.0 / DIM) ** 0.5
    t0 = time.perf_counter()
    await conn.execute(
        "INSERT INTO scale.pages(space_key) "
        "SELECT 'SP' || (g % $1) FROM generate_series(1, $2) g",
        spaces,
        max(spaces, rows // 20),  # ~20 chunk/sayfa
    )
    page_count = await conn.fetchval("SELECT count(*) FROM scale.pages")
    # vektör = küme merkezi + (satır bazında ölçeklenen) gürültü.
    # Ölçek çarpanı `f` şart: sabit gürültüde 1024 boyutta küme içi mesafeler
    # yoğunlaşır, tüm üyeler sorguya neredeyse eşit uzaklıkta olur ve "top-k"
    # keyfîleşir — ANN ile exact pratikte aynı kaliteyi verirken recall düşük
    # ölçülür (ölçüm artefaktı). Değişken f gerçek mesafe dağılımı yaratır.
    await conn.execute(
        f"""
        INSERT INTO scale.chunks(page_id, embedding)
        SELECT s.pid, c.v + nz.noise
        FROM (
            -- Sayfa ve küme BAĞIMSIZ rastgele atanır. Modüler aritmetikle
            -- (g % pages / g % clusters) atanırsa moduller birbirinin katı
            -- olduğunda küme ≡ space olur; o zaman ACL filtresi tam olarak
            -- konu kümelerini seçer — filtreli ANN için KOLAY hal. Gerçekte
            -- bir kullanıcının eriştiği dokümanlar konu uzayına dağılmıştır.
            SELECT g,
                   1 + floor(random() * {page_count})::bigint AS pid,
                   floor(random() * {clusters})::int          AS cid
            FROM generate_series(1, $1) g
        ) s
        JOIN scale.centers c ON c.id = s.cid
        CROSS JOIN LATERAL (
            -- Ölçek çarpanı fx.f LATERAL'in KENDİ FROM'unda üretilir: aggregate
            -- yalnız kendi seviyesindeki kolonlara dokunur (dış kolonu doğrudan
            -- array_agg içinde kullanmak aggregate'i dış sorguya bağlar).
            --
            -- fx içindeki `s.g` KRİTİK: LATERAL'i dış satıra BAĞIMLI kılar.
            -- Bağımlılık olmazsa Postgres alt sorguyu bir kez değerlendirip
            -- sonucu tüm satırlarda yeniden kullanır → binlerce AYNI vektör
            -- üretilir, mesafeler eşitlenir ve recall ölçümü anlamsızlaşır.
            SELECT array_agg(((random() - 0.5) * {2 * spread} * fx.f)::real)::vector AS noise
            FROM (SELECT 0.15 + random() * 1.7 AS f, s.g AS _row_dep) fx,
                 generate_series(1, {DIM})
        ) nz
        """,
        rows,
    )
    # --- Öz-denetim: veri gerçekten çeşitli mi? ---
    # Yinelenen vektörler ölçümü sessizce geçersizleştirir (mesafeler eşitlenir,
    # top-k keyfîleşir, "recall" tie-breaking gürültüsü ölçer). Erken yakala.
    sample = min(rows, 5000)
    dup = await conn.fetchval(
        f"SELECT {sample} - count(DISTINCT embedding) FROM "
        f"(SELECT embedding FROM scale.chunks LIMIT {sample}) t"
    )
    if dup > sample * 0.01:
        raise RuntimeError(
            f"Üretilen veride {dup}/{sample} yinelenen vektör var — ölçüm "
            "anlamsız olurdu. (LATERAL dış satıra bağımlı değilse Postgres "
            "gürültüyü bir kez üretip tekrar kullanır.)"
        )
    return time.perf_counter() - t0


async def build_index(conn, maintenance_mem: str, parallel_workers: int = 0) -> float:
    """HNSW index'i kurar.

    maintenance_work_mem KRİTİK: docker varsayılanı 64MB'dır ve 200k × 1024
    boyutlu vektörde (~820MB ham veri) HNSW kurulumu backend'i çökertir
    (server process exited with exit code 2 → veritabanı recovery'ye girer).
    pgvector graph'ı bellekte kurar; yetmezse ya çok yavaşlar ya da düşer.
    Bu, G-4'teki "HNSW parametreleri dokümante edilecek" maddesinin somut sebebi.
    """
    t0 = time.perf_counter()
    await conn.execute(f"SET maintenance_work_mem = '{maintenance_mem}'")
    # Paralel bakım işçileri dinamik SHARED memory kullanır; Docker'da /dev/shm
    # varsayılanı 64MB olduğundan paralel HNSW kurulumu "could not resize shared
    # memory segment ... No space left on device" ile düşer. Varsayılan 0 →
    # her ortamda çalışır. Paralel kurulum isteniyorsa compose'da shm_size
    # büyütülmeli (docker-compose.yml'de 1gb ayarlandı).
    await conn.execute(f"SET max_parallel_maintenance_workers = {parallel_workers}")
    await conn.execute(
        "CREATE INDEX scale_chunks_hnsw ON scale.chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    await conn.execute("ANALYZE scale.chunks")
    await conn.execute("ANALYZE scale.pages")
    return time.perf_counter() - t0


_SQL = """
SELECT c.id
FROM scale.chunks c
JOIN scale.pages p ON p.id = c.page_id
WHERE p.space_key = ANY($2::text[])
ORDER BY c.embedding <=> $1::vector
LIMIT $3
"""


async def _topk(conn, qvec: str, allowed: list[str], k: int, mode: str) -> tuple[list[int], float]:
    """mode: 'exact' | 'off' | 'relaxed_order' | bunların '+forced' hâli.

    '+forced' → enable_seqscan=off: planlayıcı filtreli sorguda seq scan'i
    seçtiğinde ANN yolunun ne yapacağını görmek için. Planlayıcıyı zorlamak mı
    yoksa şemayı değiştirmek mi gerektiği sorusunu bu ayırt eder.
    """
    forced = mode.endswith("+forced")
    mode = mode.removesuffix("+forced")
    async with conn.transaction():
        if mode == "exact":
            await conn.execute("SET LOCAL enable_indexscan = off")
            await conn.execute("SET LOCAL enable_bitmapscan = off")
        else:
            await conn.execute(f"SET LOCAL hnsw.iterative_scan = {mode}")
            if forced:
                await conn.execute("SET LOCAL enable_seqscan = off")
        t0 = time.perf_counter()
        rows = await conn.fetch(_SQL, qvec, allowed, k)
        ms = (time.perf_counter() - t0) * 1000
    return [r["id"] for r in rows], ms


async def _uses_index(conn, qvec: str, allowed: list[str], k: int) -> bool:
    plan = await conn.fetch("EXPLAIN " + _SQL, qvec, allowed, k)
    return any("scale_chunks_hnsw" in r[0] for r in plan)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=100_000)
    ap.add_argument("--spaces", type=int, default=200)
    ap.add_argument("--clusters", type=int, default=200)
    ap.add_argument("--queries", type=int, default=25)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--noise", type=float, default=0.3, help="gürültü NORMU (merkezler birim)")
    ap.add_argument("--selectivity", type=float, nargs="*", default=[1.0, 0.1, 0.01])
    ap.add_argument("--keep", action="store_true", help="scale şemasını bırak")
    ap.add_argument(
        "--maintenance-mem",
        default="1GB",
        help="Index kurulumu için maintenance_work_mem (64MB varsayılanı 200k'da çöküyor)",
    )
    args = ap.parse_args()

    rng = random.Random(1234)
    settings = get_settings()
    pool = await create_pool(settings.database_url)

    report: dict = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": args.rows,
        "spaces": args.spaces,
        "k": args.k,
        "cells": [],
    }

    async with pool.acquire() as conn:
        print(f"[1/4] şema + {args.clusters} küme merkezi...")
        centers = await setup(conn, args.clusters, rng)

        print(f"[2/4] {args.rows:,} chunk üretiliyor (sunucu tarafında)...")
        gen_s = await generate(conn, args.rows, args.spaces, args.clusters, args.noise)
        n = await conn.fetchval("SELECT count(*) FROM scale.chunks")
        print(f"      {n:,} chunk / {gen_s:.1f}s")

        print(f"[3/4] HNSW index kuruluyor (maintenance_work_mem={args.maintenance_mem})...")
        idx_s = await build_index(conn, args.maintenance_mem)
        size = await conn.fetchval("SELECT pg_size_pretty(pg_total_relation_size('scale.chunks'))")
        isize = await conn.fetchval(
            "SELECT pg_size_pretty(pg_relation_size('scale.scale_chunks_hnsw'))"
        )
        print(f"      index {idx_s:.1f}s · tablo {size} · index {isize}")
        report |= {"generate_s": round(gen_s, 1), "index_build_s": round(idx_s, 1),
                   "table_size": size, "index_size": isize, "chunks": n}

        all_spaces = [f"SP{i}" for i in range(args.spaces)]
        # Sorgular da küme yakınında üretilir: 1024 boyutta rastgele bir yön tüm
        # merkezlere neredeyse dik olur, "en yakın komşu" anlamsızlaşır ve recall
        # ölçümü gürültüye döner. Gerçek sorgular dokümanlara semantik olarak yakındır.
        queries = [
            _vec_literal(_perturb(rng.choice(centers), args.noise, rng))
            for _ in range(args.queries)
        ]

        print("[4/4] ölçüm...")
        for sel in args.selectivity:
            take = max(1, int(round(args.spaces * sel)))
            allowed = rng.sample(all_spaces, take)
            visible = await conn.fetchval(
                "SELECT count(*) FROM scale.chunks c JOIN scale.pages p ON p.id=c.page_id "
                "WHERE p.space_key = ANY($1::text[])",
                allowed,
            )
            used_idx = await _uses_index(conn, queries[0], allowed, args.k)

            # Tam (brute-force) referans sorgu başına BİR kez hesaplanır; iki mod
            # da aynı referansa göre puanlanır (hem doğru hem iki kat hızlı).
            exacts = [(await _topk(conn, q, allowed, args.k, "exact"))[0] for q in queries]

            for mode in ("off", "relaxed_order", "off+forced", "relaxed_order+forced"):
                recalls, lats, shortfalls = [], [], []
                for q, exact in zip(queries, exacts):
                    got, ms = await _topk(conn, q, allowed, args.k, mode)
                    lats.append(ms)
                    shortfalls.append(args.k - len(got))
                    recalls.append(
                        len(set(got) & set(exact)) / len(exact) if exact else 1.0
                    )
                cell = {
                    "selectivity": sel,
                    "allowed_spaces": take,
                    "visible_chunks": visible,
                    "mode": mode,
                    "recall": round(statistics.mean(recalls), 4),
                    "min_recall": round(min(recalls), 4),
                    "mean_shortfall": round(statistics.mean(shortfalls), 2),
                    "p95_ms": round(sorted(lats)[max(0, int(len(lats) * 0.95) - 1)], 1),
                    "index_used": used_idx,
                }
                report["cells"].append(cell)
                print(
                    f"  sel={sel:<6} görünür={visible:>8,} mode={mode:<14} "
                    f"recall={cell['recall']:.3f} (min {cell['min_recall']:.3f}) "
                    f"eksik={cell['mean_shortfall']:.1f}/{args.k} "
                    f"p95={cell['p95_ms']:.1f}ms index={used_idx}"
                )

        if not args.keep:
            await conn.execute("DROP SCHEMA scale CASCADE")

    await pool.close()

    out = ROOT / "eval" / "results" / f"scale-test-{args.rows}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSonuç: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
