# Kurumsal RAG Platformu

ACL'e tam saygılı, kaynak gösteren, izlenebilir kurumsal RAG platformu.
Detaylı yol haritası ve mimari kararlar için: **[PROJE-PLANI.md](PROJE-PLANI.md)**

## Şu anki durum: Faz 0 — G-1 ✅ · G-2 ✅ (ADR-3 kapandı: bge-m3)

Bu repo planın en kritik doğrulamasını içerir: **ACL-filtered hybrid retrieval** (G-1),
ve embedding/reranker seçimini (G-2 → ADR-3).

- **ACL pre-filter (ADR-4):** OpenFGA `ListObjects` → kullanıcının erişim seti →
  SQL'de metadata filtresi. Post-filter yok; izinsiz içerik aday listesine giremez.
- **Hybrid arama:** pgvector HNSW (dense) + Postgres FTS `turkish_unaccent` (lexical),
  RRF füzyonu, ardından cross-encoder reranker (bge-reranker-v2-m3).
- **Sentetik veri:** Gerçek Confluence erişimi henüz yok → 3 space, **40 sayfa**
  (confusable kümeler), 6 kullanıcı, 7 gruplu gerçekçi Türkçe kurum senaryosu
  (`scripts/synthetic_corpus.py`).
- **Embedding (ADR-3 ✅ bge-m3):** Varsayılan `fake` (deterministik, sadece ACL/latency
  testi için). Seçilen model: `local` (sentence-transformers, **GPU otomatik**) veya
  `openai` (vLLM/OpenAI-uyumlu endpoint — üretim hedefi). Karşılaştırma raporu:
  [`eval/results/g2-report.md`](eval/results/g2-report.md).

  ```powershell
  # G-2 karşılaştırma matrisi: bge-m3 vs Qwen3 × noop vs reranker + token verimi
  # (GPU'da otomatik fp16; ilk koşuda modeller iner ~3.4GB):
  pip install -e ".[local]"
  python scripts/run_g2_matrix.py          # -> eval/results/g2-report.md

  # veya tek model ile index + eval:
  $env:EMBEDDINGS_PROVIDER='local'; $env:EMBEDDINGS_MODEL='BAAI/bge-m3'
  $env:RERANKER_PROVIDER='local'           # cross-encoder reranker'ı aç
  python scripts/seed_synthetic.py
  python scripts/run_eval.py --golden eval/golden/golden_v2.jsonl
  ```

## Kurulum

Ön koşul: Docker Desktop, Python 3.11+

```powershell
# 1) Altyapı (Postgres+pgvector, OpenFGA)
docker compose up -d

# 2) Python ortamı
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 3) Sentetik veri + izinler
python scripts/seed_synthetic.py

# 4) G-1 kabul testi: sızıntı = 0 + latency
python scripts/acl_leak_test.py
```

## Kullanım

```powershell
# CLI ile hızlı sorgu (kullanıcı bazlı ACL uygulanır)
python scripts/dev_query.py ayse "yıllık izin kaç gün"
python scripts/dev_query.py zeynep "maaş bantları"     # kısıtlı sayfayı sadece zeynep görür
python scripts/dev_query.py mehmet "maaş bantları"     # mehmet göremez

# API
uvicorn ragplatform.api.main:app --port 8000
# POST http://localhost:8000/v1/retrieve  {"query": "...", "user_id": "ayse"}
```

## Testler

```powershell
pytest                              # birim testleri (servis gerektirmez)
python scripts/acl_leak_test.py     # entegrasyon: G-1 kabul kriteri
python scripts/run_eval.py          # golden set eval: hit@k / MRR / yetki-sınırı (G-3)
```

Golden set formatı ve kuralları: [eval/golden/README.md](eval/golden/README.md).
Eval sonuçları `eval/results/` altına yazılır ve baseline takibi için commit'lenir.

## Dizin yapısı

```
src/ragplatform/
  acl/          OpenFGA istemcisi + erişim seti çözümü (ADR-4)
  embeddings/   fake (test) / openai-uyumlu (vLLM) sağlayıcılar
  ingestion/    chunker (Faz 1'de Docling ile değişecek) + indexer
  retrieval/    hybrid arama + RRF + reranker arayüzü + servis
  api/          FastAPI retrieval servisi
infra/
  db/init/      Postgres şeması (pgvector + turkish_unaccent FTS)
  openfga/      yetki modeli (DSL + JSON)
scripts/        seed, leak testi, dev CLI
tests/          birim testleri
```

## Bilinçli sınırlar (Faz 0)

- Reranker: bge-reranker-v2-m3 cross-encoder uygulandı ve G-2'de ölçüldü
  (`RERANKER_PROVIDER=local`); varsayılan hâlâ `noop`. Üretimde ayrı vLLM/servis
  havuzuna taşınacak (şimdilik in-process, yerel model).
- `user_id` istek gövdesinde — Faz 1'de OIDC token'dan gelecek.
- Generation (LLM cevabı) yok — bu servis yalnız retrieval; LLM, LiteLLM gateway
  arkasına Faz 1'de eklenecek.
- Erişim seti cache'i in-process TTL — Faz 1'de kalıcı materializasyon + izin senkronu.
