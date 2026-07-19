# G-2 / ADR-3 — Embedding + reranker karşılaştırma raporu

> Üretim: `scripts/run_g2_matrix.py` · 2026-07-19T14:18:21+00:00
> Golden: `golden_v2.jsonl` · Korpus: 40 sayfa (confusable kümeler) · top_k=8

## Karşılaştırma matrisi

| embedding | reranker | MRR | hit@1 | hit@3 | hit@5 | parafraz@5 | p95 ms | ACL ihlal |
|---|---|---|---|---|---|---|---|---|
| bge-m3 | noop | 0.937 | 0.919 | 0.973 | 0.973 | 0.909 | 115.1 | 0 |
| bge-m3 | bge-reranker-v2-m3 | 0.969 | 0.946 | 1.000 | 1.000 | 1.000 | 148.6 | 0 |
| qwen3-0.6b | noop | 0.896 | 0.838 | 0.973 | 0.973 | 0.909 | 163.8 | 0 |
| qwen3-0.6b | bge-reranker-v2-m3 | 0.969 | 0.946 | 1.000 | 1.000 | 1.000 | 254.1 | 0 |

## Kategori bazında hit@5

| embedding | reranker | faktuel | kisitli-erisim | parafraz |
|---|---|---|---|---|
| bge-m3 | noop | 1.000 | 1.000 | 0.909 |
| bge-m3 | bge-reranker-v2-m3 | 1.000 | 1.000 | 1.000 |
| qwen3-0.6b | noop | 1.000 | 1.000 | 0.909 |
| qwen3-0.6b | bge-reranker-v2-m3 | 1.000 | 1.000 | 1.000 |

## ADR-3 önerisi

**Önerilen embedding modeli: `bge-m3`** (rerank'siz MRR=0.937, parafraz hit@5=0.909).
- `qwen3-0.6b`: rerank'siz MRR=0.896, parafraz hit@5=0.909.

**Reranker (bge-reranker-v2-m3) etkisi** (`bge-m3` üzerinde): MRR 0.937→0.969 (Δ+0.032), hit@1 0.919→0.946, p95 115.1→148.6ms — katkı sağlıyor → açılması önerilir.

## Türkçe token verimliliği

Korpus: 2693 kelime, 19928 karakter.

| model | tokens | tok/kelime | tok/karakter | vocab |
|---|---|---|---|---|
| BAAI/bge-m3 | 4737 | 1.759 | 0.2377 | 250002 |
| Qwen/Qwen3-Embedding-0.6B | 7046 | 2.616 | 0.3536 | 151643 |

## ACL
Matris genelinde toplam yetki-sınırı ihlali: **0** (temiz).
