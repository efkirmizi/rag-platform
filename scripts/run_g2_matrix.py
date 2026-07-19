# -*- coding: utf-8 -*-
"""G-2 karşılaştırma matrisi (ADR-3'ü kapatan çıktı).

{bge-m3, Qwen3-Embedding-0.6B} × {noop, bge-reranker-v2-m3} matrisini golden_v2
üzerinde ölçer. Embedding değişimi re-index gerektirir (chunk vektörleri modele
bağlı); reranker query-time olduğundan re-index gerektirmez → toplam 2 re-index.

Adımlar:
  1) OpenFGA'yı 40-sayfalık korpusun tuple'larıyla taze bootstrap et.
  2) Her embedding modeli için: GPU'ya yükle → index_corpus → her reranker için
     golden_v2'yi score_run'dan geçir.
  3) matris JSON + markdown rapor (karşılaştırma tablosu + ADR-3 önerisi) yaz.

Ön koşul: docker compose up -d  (postgres + openfga ayakta), GPU + `.[local]`.
Çalıştırma: python scripts/run_g2_matrix.py [--top-k 8]

İlk koşuda modeller iner (bge-m3 ~2.3GB, Qwen3 ~1.2GB, reranker ~2.2GB).
"""

import argparse
import asyncio
import gc
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import synthetic_corpus as corpus
from run_eval import score_run
from seed_synthetic import bootstrap_fga, index_corpus

from ragplatform.acl.access import AccessResolver
from ragplatform.acl.fga import FgaClient
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings.local_st import LocalSTEmbeddings
from ragplatform.retrieval.rerank import CrossEncoderReranker, NoopReranker
from ragplatform.retrieval.service import RetrievalService

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOLDEN = ROOT / "eval" / "golden" / "golden_v2.jsonl"

# Karşılaştırılacak embedding modelleri (ikisi de 1024-dim → şema değişmez).
EMBEDDINGS = [
    {"key": "bge-m3", "model": "BAAI/bge-m3"},
    {"key": "qwen3-0.6b", "model": "Qwen/Qwen3-Embedding-0.6B"},
]
RERANKERS = ["noop", "bge-reranker-v2-m3"]


def _free_gpu(*objs) -> None:
    """Model referanslarını bırak + CUDA cache'i boşalt (6GB VRAM'de fragmentasyona karşı)."""
    for o in objs:
        for attr in ("_model", "_scorer"):
            if hasattr(o, attr):
                setattr(o, attr, None)
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _build_reranker(key: str, settings):
    if key == "noop":
        return NoopReranker()
    return CrossEncoderReranker(
        model_name="BAAI/bge-reranker-v2-m3",
        device=settings.embeddings_device,
        dtype=settings.embeddings_dtype,
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    items = [
        json.loads(line)
        for line in GOLDEN.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    settings = get_settings()

    pool = await create_pool(settings.database_url)
    # FGA'yı 40-sayfalık korpusa göre taze yaz (yeni kısıtlı sayfaların tuple'ları dahil).
    await bootstrap_fga(settings)
    fga = FgaClient.from_settings(settings)
    resolver = AccessResolver(fga, ttl_seconds=settings.acl_cache_ttl_seconds)

    cells: list[dict] = []
    try:
        for emb_cfg in EMBEDDINGS:
            print(f"\n=== embedding: {emb_cfg['key']} ({emb_cfg['model']}) — index + eval ===")
            embedder = LocalSTEmbeddings(
                model_name=emb_cfg["model"],
                dim=settings.embeddings_dim,
                device=settings.embeddings_device,
                dtype=settings.embeddings_dtype,
            )
            await index_corpus(pool, embedder)
            resolver.invalidate()  # ACL modelden bağımsız ama taze bootstrap sonrası temiz başla

            for rr_key in RERANKERS:
                reranker = _build_reranker(rr_key, settings)
                service = RetrievalService(pool, embedder, resolver, reranker)
                summary = await score_run(
                    service,
                    items,
                    args.top_k,
                    golden_name=GOLDEN.name,
                    embedding_model=embedder.name,
                    reranker_name=getattr(reranker, "name", rr_key),
                )
                m = summary["metrics"]
                print(
                    f"  [{emb_cfg['key']} × {rr_key}] MRR={m['mrr']:.3f} "
                    f"hit@1={m['hit@1']:.3f} hit@5={m['hit@5']:.3f} "
                    f"parafraz@5={summary['per_category'].get('parafraz', {}).get('hit@5', 0):.3f} "
                    f"p95={m['latency_p95_ms']}ms acl_ihlal={m['acl_violations']}"
                )
                cells.append({"embedding": emb_cfg["key"], "reranker": rr_key, "summary": summary})
                if rr_key != "noop":
                    _free_gpu(reranker)

            _free_gpu(embedder)
            await embedder.close()
    finally:
        await fga.close()
        await pool.close()

    # --- Token verimliliği (opsiyonel; tokenizer indirmesi gerektirir) ---
    token_eff = None
    try:
        from token_efficiency import corpus_texts, measure

        token_eff = measure([e["model"] for e in EMBEDDINGS], corpus_texts())
    except Exception as e:  # matris sonucunu token ölçümü başarısızlığına feda etme
        print(f"[uyari] token verimliliği ölçülemedi: {e}")

    _write_outputs(cells, token_eff, args.top_k)

    total_viol = sum(c["summary"]["metrics"]["acl_violations"] for c in cells)
    if total_viol:
        print(f"\n❌ {total_viol} ACL ihlali (matris genelinde) — rapora bakın")
        return 1
    return 0


def _cell(cells, emb, rr):
    return next(c for c in cells if c["embedding"] == emb and c["reranker"] == rr)


def _recommend(cells) -> str:
    """noop reranker'da embedding modellerini karşılaştırıp ADR-3 önerisi üretir."""
    def mrr(emb, rr):
        return _cell(cells, emb, rr)["summary"]["metrics"]["mrr"]

    def para(emb, rr):
        return _cell(cells, emb, rr)["summary"]["per_category"].get("parafraz", {}).get("hit@5", 0)

    embs = [e["key"] for e in EMBEDDINGS]
    # Embedding kalitesi rerank'siz izole edilir (noop):
    ranked = sorted(embs, key=lambda e: (mrr(e, "noop"), para(e, "noop")), reverse=True)
    best = ranked[0]
    lines = []
    lines.append(f"**Önerilen embedding modeli: `{best}`** "
                 f"(rerank'siz MRR={mrr(best, 'noop'):.3f}, parafraz hit@5={para(best, 'noop'):.3f}).")
    other = [e for e in embs if e != best]
    for o in other:
        lines.append(f"- `{o}`: rerank'siz MRR={mrr(o, 'noop'):.3f}, "
                     f"parafraz hit@5={para(o, 'noop'):.3f}.")
    # Reranker etkisi (kazanan embedding üzerinde):
    d_mrr = mrr(best, "bge-reranker-v2-m3") - mrr(best, "noop")
    b_noop = _cell(cells, best, "noop")["summary"]["metrics"]
    b_rr = _cell(cells, best, "bge-reranker-v2-m3")["summary"]["metrics"]
    verdict = "katkı sağlıyor → açılması önerilir" if d_mrr > 0.005 else (
        "anlamlı katkı yok (bu sette)" if abs(d_mrr) <= 0.005 else "skoru düşürüyor")
    lines.append(
        f"\n**Reranker (bge-reranker-v2-m3) etkisi** (`{best}` üzerinde): "
        f"MRR {b_noop['mrr']:.3f}→{b_rr['mrr']:.3f} (Δ{d_mrr:+.3f}), "
        f"hit@1 {b_noop['hit@1']:.3f}→{b_rr['hit@1']:.3f}, "
        f"p95 {b_noop['latency_p95_ms']}→{b_rr['latency_p95_ms']}ms — {verdict}."
    )
    return "\n".join(lines)


def _write_outputs(cells, token_eff, top_k) -> None:
    results_dir = ROOT / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    matrix = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "golden_file": GOLDEN.name,
        "corpus_pages": len(corpus.PAGES),
        "top_k": top_k,
        "embeddings": [e["key"] for e in EMBEDDINGS],
        "rerankers": RERANKERS,
        "cells": cells,
        "token_efficiency": token_eff,
    }
    (results_dir / f"{stamp}_g2_matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- Markdown rapor ---
    lines = [
        "# G-2 / ADR-3 — Embedding + reranker karşılaştırma raporu",
        "",
        f"> Üretim: `scripts/run_g2_matrix.py` · {matrix['run_at']}",
        f"> Golden: `{GOLDEN.name}` · Korpus: {len(corpus.PAGES)} sayfa (confusable kümeler) · top_k={top_k}",
        "",
        "## Karşılaştırma matrisi",
        "",
        "| embedding | reranker | MRR | hit@1 | hit@3 | hit@5 | parafraz@5 | p95 ms | ACL ihlal |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        m = c["summary"]["metrics"]
        para = c["summary"]["per_category"].get("parafraz", {}).get("hit@5", 0)
        lines.append(
            f"| {c['embedding']} | {c['reranker']} | {m['mrr']:.3f} | {m['hit@1']:.3f} | "
            f"{m['hit@3']:.3f} | {m['hit@5']:.3f} | {para:.3f} | {m['latency_p95_ms']} | "
            f"{m['acl_violations']} |"
        )

    lines += ["", "## Kategori bazında hit@5", "",
              "| embedding | reranker | " + " | ".join(
                  sorted({cat for c in cells for cat in c["summary"]["per_category"]})) + " |"]
    cats = sorted({cat for c in cells for cat in c["summary"]["per_category"]})
    lines.append("|---|---|" + "|".join(["---"] * len(cats)) + "|")
    for c in cells:
        pc = c["summary"]["per_category"]
        row = " | ".join(f"{pc.get(cat, {}).get('hit@5', 0):.3f}" for cat in cats)
        lines.append(f"| {c['embedding']} | {c['reranker']} | {row} |")

    lines += ["", "## ADR-3 önerisi", "", _recommend(cells)]

    if token_eff:
        lines += ["", "## Türkçe token verimliliği", "",
                  f"Korpus: {token_eff['words']} kelime, {token_eff['chars']} karakter.", "",
                  "| model | tokens | tok/kelime | tok/karakter | vocab |",
                  "|---|---|---|---|---|"]
        for name, tm in token_eff["models"].items():
            lines.append(
                f"| {name} | {tm['tokens']} | {tm['tokens_per_word']} | "
                f"{tm['tokens_per_char']} | {tm['vocab_size']} |"
            )

    total_viol = sum(c["summary"]["metrics"]["acl_violations"] for c in cells)
    lines += ["", "## ACL",
              f"Matris genelinde toplam yetki-sınırı ihlali: **{total_viol}** "
              f"({'temiz' if total_viol == 0 else 'İHLAL VAR — incele'})."]

    report = results_dir / "g2-report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nRapor : {report.relative_to(ROOT)}")
    print(f"Matris: eval/results/{stamp}_g2_matrix.json")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
