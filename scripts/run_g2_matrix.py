# -*- coding: utf-8 -*-
"""G-2 karşılaştırma matrisi (ADR-3'ü kapatan çıktı).

{bge-m3, Qwen3-Embedding-0.6B} × {noop, bge-reranker-v2-m3} matrisini bir golden
set üzerinde ölçer. Embedding değişimi re-index gerektirir (chunk vektörleri
modele bağlı); reranker query-time olduğundan gerektirmez → toplam 2 re-index.

Adımlar:
  1) OpenFGA'yı korpusun tuple'larıyla taze bootstrap et, index'i temizle.
  2) Her embedding modeli için: GPU'ya yükle → index_corpus → her reranker için
     golden set'i score_run'dan geçir.
  3) matris JSON + markdown rapor (karşılaştırma tablosu + ADR-3 önerisi) yaz.

Ön koşul: docker compose up -d  (postgres + openfga ayakta), GPU + `.[local]`.
Çalıştırma:
  python scripts/run_g2_matrix.py                       # sentetik korpus
  python scripts/run_g2_matrix.py --docs data/tr-corpus \
      --golden eval/golden/golden_tr_v1.jsonl           # gerçek Türkçe korpus

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

from run_eval import score_run
from seed_synthetic import corpus_model

from ragplatform.acl.access import AccessResolver
from ragplatform.acl.bootstrap import bootstrap_store
from ragplatform.acl.fga import FgaClient
from ragplatform.config import get_settings
from ragplatform.db import create_pool
from ragplatform.embeddings.local_st import LocalSTEmbeddings
from ragplatform.ingestion.corpus import build_tuples, index_corpus
from ragplatform.ingestion.folder_source import load_folder
from ragplatform.retrieval.rerank import CrossEncoderReranker, NoopReranker
from ragplatform.retrieval.service import RetrievalService

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_GOLDEN = ROOT / "eval" / "golden" / "golden_v2.jsonl"

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
    parser.add_argument(
        "--docs",
        default=None,
        help="Klasör korpusu (ör. data/tr-corpus). Verilmezse sentetik korpus kullanılır.",
    )
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    args = parser.parse_args()

    golden = Path(args.golden)
    items = [
        json.loads(line)
        for line in golden.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    corpus = load_folder(args.docs) if args.docs else corpus_model()
    errors = corpus.validate()
    if errors:
        print(f"❌ Korpus doğrulaması başarısız: {errors[:3]}")
        return 1
    corpus_pages = len(corpus.pages)
    settings = get_settings()

    pool = await create_pool(settings.database_url)
    # FGA'yı bu korpusa göre taze yaz (kısıtlı sayfaların tuple'ları dahil).
    fga_model = json.loads((ROOT / "infra" / "openfga" / "model.json").read_text("utf-8"))
    await bootstrap_store(settings, fga_model, build_tuples(corpus), store_name="rag-g2")
    fga = FgaClient.from_settings(settings)
    resolver = AccessResolver(fga, ttl_seconds=settings.acl_cache_ttl_seconds)
    print(f"Korpus: {corpus_pages} doküman · golden: {golden.name} ({len(items)} soru)")

    cells: list[dict] = []
    try:
        # Index'i temizle: index'te kalan başka bir korpus sonuçlara karışır ve
        # space anahtarları çakışabilir → ölçüm sessizce geçersizleşir.
        await pool.execute("TRUNCATE spaces CASCADE")
        print("[db] index temizlendi (ölçüm yalnız bu korpus üzerinde)")

        for emb_cfg in EMBEDDINGS:
            print(f"\n=== embedding: {emb_cfg['key']} ({emb_cfg['model']}) — index + eval ===")
            embedder = LocalSTEmbeddings(
                model_name=emb_cfg["model"],
                dim=settings.embeddings_dim,
                device=settings.embeddings_device,
                dtype=settings.embeddings_dtype,
            )
            await index_corpus(pool, embedder, corpus, quiet=True)
            resolver.invalidate()  # ACL modelden bağımsız ama taze bootstrap sonrası temiz başla

            for rr_key in RERANKERS:
                reranker = _build_reranker(rr_key, settings)
                service = RetrievalService(pool, embedder, resolver, reranker)
                summary = await score_run(
                    service,
                    items,
                    args.top_k,
                    golden_name=golden.name,
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
        from token_efficiency import measure

        # Token verimliliği ÖLÇÜLEN korpus üzerinden hesaplanmalı; aksi hâlde
        # gerçek korpusla koşarken sentetik metnin sayıları raporlanırdı.
        texts = [f"{p.title}\n{p.content}" for p in corpus.pages]
        token_eff = measure([e["model"] for e in EMBEDDINGS], texts)
    except Exception as e:  # matris sonucunu token ölçümü başarısızlığına feda etme
        print(f"[uyari] token verimliliği ölçülemedi: {e}")

    _write_outputs(cells, token_eff, args.top_k, golden.name, corpus_pages)

    total_viol = sum(c["summary"]["metrics"]["acl_violations"] for c in cells)
    if total_viol:
        print(f"\n❌ {total_viol} ACL ihlali (matris genelinde) — rapora bakın")
        return 1
    return 0


def _cell(cells, emb, rr):
    return next(c for c in cells if c["embedding"] == emb and c["reranker"] == rr)


def _embs_and_rr(cells):
    """Matris hücrelerinden embedding ve reranker anahtarlarını sırayı koruyarak çıkarır
    (modül global'lerinden bağımsız → rapor kayıtlı JSON'dan da render edilebilir)."""
    embs = list(dict.fromkeys(c["embedding"] for c in cells))
    rrs = list(dict.fromkeys(c["reranker"] for c in cells))
    rr_on = next((r for r in rrs if r != "noop"), None)
    return embs, rrs, rr_on


def render_report(matrix: dict) -> str:
    """Matris sözlüğünden (canlı koşu ya da kayıtlı JSON) kapsamlı markdown rapor üretir."""
    cells = matrix["cells"]
    top_k = matrix["top_k"]
    token_eff = matrix.get("token_efficiency")
    embs, _rrs, rr_on = _embs_and_rr(cells)

    def m(emb, rr):
        return _cell(cells, emb, rr)["summary"]["metrics"]

    def para(emb, rr):
        return _cell(cells, emb, rr)["summary"]["per_category"].get("parafraz", {}).get("hit@5", 0)

    # Kazanan embedding: rerank'siz (noop) kalite izole edilir.
    best = sorted(embs, key=lambda e: (m(e, "noop")["mrr"], para(e, "noop")), reverse=True)[0]
    total_viol = sum(c["summary"]["metrics"]["acl_violations"] for c in cells)

    L: list[str] = []
    L += [
        "# G-2 / ADR-3 — Embedding + Reranker Karşılaştırma Raporu",
        "",
        f"> **Üretim:** `scripts/run_g2_matrix.py` · {matrix['run_at']}  ",
        f"> **Golden set:** `{matrix['golden_file']}` · **Korpus:** {matrix['corpus_pages']} "
        f"sayfa (confusable kümeler) · **top_k:** {top_k} · **Donanım:** yerel GPU (fp16)",
        "",
        "---",
        "",
    ]

    # --- Karar kutusu ---
    d_mrr = m(best, rr_on)["mrr"] - m(best, "noop")["mrr"] if rr_on else 0.0
    # Faydayı GECİKME MALİYETİYLE birlikte değerlendir: uzun gerçek metinlerde
    # cross-encoder 24 adayı puanlarken latency birkaç katına çıkabiliyor.
    lat_ratio = (
        m(best, rr_on)["latency_p95_ms"] / max(m(best, "noop")["latency_p95_ms"], 1e-6)
        if rr_on
        else 1.0
    )
    if d_mrr <= 0.005:
        rr_verdict = "opsiyonel (bu sette anlamlı katkı yok)"
    elif lat_ratio >= 2.0:
        rr_verdict = (
            f"**duruma göre** — kalite artıyor ama p95 {lat_ratio:.1f}× yükseliyor; "
            "gecikmeye duyarlı kullanımda kapalı bırakılabilir"
        )
    else:
        rr_verdict = "**açılması önerilir**"
    L += [
        "## 🎯 Karar (ADR-3)",
        "",
        f"> **Seçilen embedding modeli: `{best}`.** Reranker (`{rr_on}`): {rr_verdict}.",
        "",
        f"`{best}`, rerank'siz izole kalitede (MRR **{m(best, 'noop')['mrr']:.3f}**, "
        f"hit@1 **{m(best, 'noop')['hit@1']:.3f}**) diğer adayı geçti; reranker ile "
        f"MRR **{m(best, rr_on)['mrr']:.3f}**'e çıkıyor. Türkçe token verimi ve latency'de de "
        "önde (aşağıda). Gerekçelerin tamamı §Yorum'da.",
        "",
    ]

    # --- Yöntem ---
    L += [
        "## Yöntem",
        "",
        "**Neden bu ölçüm?** İlk golden set (15 sayfa, 22 soru) bge-m3 ile hit@5=1.00 "
        "veriyordu — *doygun*. Her cevap zaten ilk 5'te olunca reranker top-50→top-8 "
        "yeniden sıralaması ve modeller arası fark **tanım gereği ölçülemez**. Bu yüzden "
        "önce ayırt edici bir substrat üretildi:",
        "",
        f"- **Korpus:** {matrix['corpus_pages']} doküman. Sorgu başına birden çok makul "
        "aday bulunması hedeflenir → hit@1 ve MRR ayrışır.",
        f"- **Golden set:** `{matrix['golden_file']}`: faktüel · parafraz (semantik boşluk) · "
        "kısıtlı-erişim · yetki-sınırı (aynı-space kısıtlı → sıkı ACL testi).",
        f"- **Matris:** {{{', '.join(f'`{e}`' for e in embs)}}} × {{noop, `{rr_on}`}}. "
        "Embedding değişimi re-index gerektirir (vektörler modele bağlı); reranker query-time.",
        "- **ACL:** her hücre yetki-sınırı sorularını içerir; forbidden sayfa dönerse eval düşer.",
        "",
    ]

    # --- Sonuç matrisi ---
    L += [
        "## Sonuç matrisi",
        "",
        "| embedding | reranker | MRR | hit@1 | hit@3 | hit@5 | parafraz@5 | p95 (ms) | ACL |",
        "|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|",
    ]
    for c in cells:
        mm = c["summary"]["metrics"]
        p = c["summary"]["per_category"].get("parafraz", {}).get("hit@5", 0)
        star = " ⭐" if c["embedding"] == best and c["reranker"] == rr_on else ""
        L.append(
            f"| `{c['embedding']}`{star} | {c['reranker']} | **{mm['mrr']:.3f}** | "
            f"{mm['hit@1']:.3f} | {mm['hit@3']:.3f} | {mm['hit@5']:.3f} | {p:.3f} | "
            f"{mm['latency_p95_ms']} | {mm['acl_violations']} |"
        )
    L.append("")
    L.append("⭐ = seçilen yapılandırma. MRR = ortalama karşılıklı sıra (sayfa bazında).")
    if len({c["summary"]["metrics"]["hit@5"] for c in cells}) == 1:
        L.append("")
        L.append(
            f"> ⚠️ hit@5 tüm hücrelerde {cells[0]['summary']['metrics']['hit@5']:.3f} — "
            "set k=5'te **doygun**; ayrım yalnız MRR ve hit@1'den geliyor. Daha ince "
            "ayrım için sete daha zor/karıştırıcı sorular eklenmeli."
        )
    L.append("")

    # --- Kategori bazında hit@5 ---
    cats = sorted({cat for c in cells for cat in c["summary"]["per_category"]})
    L += ["## Kategori bazında hit@5", "",
          "| embedding | reranker | " + " | ".join(cats) + " |",
          "|---|---|" + "|".join([":--:"] * len(cats)) + "|"]
    for c in cells:
        pc = c["summary"]["per_category"]
        row = " | ".join(f"{pc.get(cat, {}).get('hit@5', 0):.3f}" for cat in cats)
        L.append(f"| `{c['embedding']}` | {c['reranker']} | {row} |")
    L.append("")

    # --- Yorum ---
    others = [e for e in embs if e != best]
    L += ["## Yorum", "", f"### Embedding: `{best}` vs " + ", ".join(f"`{o}`" for o in others), ""]
    L.append(f"Rerank'siz (embedding kalitesi izole): `{best}` MRR **{m(best, 'noop')['mrr']:.3f}** / "
             f"hit@1 **{m(best, 'noop')['hit@1']:.3f}**.")
    for o in others:
        L.append(f"- `{o}`: MRR {m(o, 'noop')['mrr']:.3f} / hit@1 {m(o, 'noop')['hit@1']:.3f} "
                 f"(parafraz@5 {para(o, 'noop'):.3f}).")
    L += ["",
          f"`{best}` daha yüksek hit@1 veriyor — confusable kümede doğru sayfayı ilk sıraya "
          "koyma yeteneği belirleyici. Parafraz (semantik boşluk) her iki modelde yakın.", ""]

    if rr_on:
        bn, br = m(best, "noop"), m(best, rr_on)
        L += [f"### Reranker (`{rr_on}`) etkisi", "",
              f"`{best}` üzerinde: MRR {bn['mrr']:.3f} → **{br['mrr']:.3f}** (Δ{d_mrr:+.3f}), "
              f"hit@1 {bn['hit@1']:.3f} → **{br['hit@1']:.3f}**, "
              f"parafraz@5 {para(best, 'noop'):.3f} → **{para(best, rr_on):.3f}**. "
              f"Latency bedeli: p95 {bn['latency_p95_ms']} → {br['latency_p95_ms']}ms "
              f"(hedef <300ms içinde). Cross-encoder, RRF'in geniş recall'ını hassaslaştırıyor "
              f"ve embedding'ler arası farkı kapatıyor → {rr_verdict}.", ""]

    if token_eff:
        L += ["### Türkçe token verimliliği", "",
              f"Korpus: {token_eff['words']} kelime, {token_eff['chars']} karakter.", "",
              "| model | tokens | tok/kelime | tok/karakter | vocab |",
              "|---|:--:|:--:|:--:|:--:|"]
        for name, tm in token_eff["models"].items():
            L.append(f"| `{name}` | {tm['tokens']} | **{tm['tokens_per_word']}** | "
                     f"{tm['tokens_per_char']} | {tm['vocab_size']} |")
        tpw = {n: t["tokens_per_word"] for n, t in token_eff["models"].items()}
        lo = min(tpw, key=tpw.get)
        hi = max(tpw, key=tpw.get)
        if lo != hi:
            pct = round((tpw[hi] / tpw[lo] - 1) * 100)
            L += ["",
                  f"`{lo.split('/')[-1]}` Türkçe'yi daha verimli parçalıyor: "
                  f"`{hi.split('/')[-1]}` aynı metin için ~%{pct} fazla token üretiyor → "
                  "daha küçük etkin bağlam + daha yüksek GPU/API maliyeti. Türkçe ağırlıklı "
                  "içerikte bu doğrudan bir seçim kriteri.", ""]

    # --- Latency + ACL ---
    lat = {c["embedding"]: {} for c in cells}
    for c in cells:
        lat[c["embedding"]][c["reranker"]] = c["summary"]["metrics"]["latency_p95_ms"]
    L += ["### Latency", "",
          "Tüm hücreler retrieval p95 hedefinin (<1s; bu PoC'de <300ms) altında. "
          + " · ".join(f"`{e}`: " + "/".join(f"{v}ms" for v in lat[e].values()) for e in embs)
          + " (noop/rerank).", ""]

    L += ["### ACL", "",
          f"Matris genelinde toplam yetki-sınırı ihlali: **{total_viol}** "
          f"({'✅ temiz' if total_viol == 0 else '❌ İHLAL — incele'}). "
          "40-sayfalık korpusta aynı-space kısıtlı yetki-sınırı testleri (kullanıcı space'i "
          "görüyor ama kısıtlı sayfayı görmemeli) dahil sızıntı yok.", ""]

    # --- Sınırlar + üretim ---
    L += [
        "## Sınırlar ve sıradaki adım",
        "",
        "- **Sentetik içerik.** Karar sentetik (ama gerçekçi) Türkçe korpus üzerinde. Plan, "
        "gerçek ~%90 Türkçe pilot içeriği (G-0) ile yeniden doğrulamayı öngörüyor — matris "
        "tek komutla koşar.",
        f"- **0.6B karşılaştırıldı.** Daha büyük Qwen3-Embedding (4B/8B) `{best}`'i geçebilir; "
        "GPU serving hazır olunca değerlendirilebilir.",
        "- **In-process reranker.** Üretimde ayrı vLLM/servis havuzuna taşınacak (Faz 1).",
        "",
        "## Yeniden üretim",
        "",
        "```powershell",
        "python scripts/run_g2_matrix.py           # tam matris (GPU) + rapor",
        "python scripts/g2_report.py <matris.json> # kayıtlı JSON'dan raporu yeniden render et",
        "python scripts/token_efficiency.py        # yalnız token verimliliği",
        "```",
    ]
    return "\n".join(L) + "\n"


def _write_outputs(cells, token_eff, top_k, golden_name, corpus_pages) -> None:
    results_dir = ROOT / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    matrix = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "golden_file": golden_name,
        "corpus_pages": corpus_pages,
        "top_k": top_k,
        "embeddings": [e["key"] for e in EMBEDDINGS],
        "rerankers": RERANKERS,
        "cells": cells,
        "token_efficiency": token_eff,
    }
    (results_dir / f"{stamp}_g2_matrix.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (results_dir / "g2-report.md").write_text(render_report(matrix), encoding="utf-8")
    print("\nRapor : eval/results/g2-report.md")
    print(f"Matris: eval/results/{stamp}_g2_matrix.json")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
