# Kurumsal RAG Platformu

ACL'e tam saygılı, kaynak gösteren, izlenebilir kurumsal RAG platformu.
Detaylı yol haritası ve mimari kararlar için: **[PROJE-PLANI.md](PROJE-PLANI.md)**

## Şu anki durum: Faz 0 — G-1 PoC

Bu repo şu an planın en kritik doğrulamasını içerir: **ACL-filtered hybrid retrieval**.

- **ACL pre-filter (ADR-4):** OpenFGA `ListObjects` → kullanıcının erişim seti →
  SQL'de metadata filtresi. Post-filter yok; izinsiz içerik aday listesine giremez.
- **Hybrid arama:** pgvector HNSW (dense) + Postgres FTS `turkish_unaccent` (lexical),
  RRF füzyonu.
- **Sentetik veri:** Gerçek Confluence erişimi henüz yok → 3 space, 15 sayfa,
  6 kullanıcı, 7 gruplu gerçekçi Türkçe kurum senaryosu (`scripts/synthetic_corpus.py`).
- **Embedding:** Varsayılan `fake` (deterministik, sadece ACL/latency testi için).
  Gerçek model bağlamak için `.env` içinde `EMBEDDINGS_PROVIDER=openai` +
  vLLM/OpenAI-uyumlu endpoint verin (G-2).

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
```

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

- Reranker `Noop` — Faz 1'de bge-reranker-v2-m3 bağlanacak (arayüz hazır).
- `user_id` istek gövdesinde — Faz 1'de OIDC token'dan gelecek.
- Generation (LLM cevabı) yok — bu servis yalnız retrieval; LLM, LiteLLM gateway
  arkasına Faz 1'de eklenecek.
- Erişim seti cache'i in-process TTL — Faz 1'de kalıcı materializasyon + izin senkronu.
