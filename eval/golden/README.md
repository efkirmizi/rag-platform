# Golden eval seti

Retrieval kalitesinin **tek doğruluk kaynağı**. Her prompt/model/chunking değişikliği
bu set üzerinde ölçülür; skor düşüren değişiklik prod'a çıkamaz (ADR-7, Faz 2'de CI kapısı).

## Format (`golden_v1.jsonl` — satır başına bir JSON)

| Alan | Açıklama |
|---|---|
| `id` | Benzersiz kısa kimlik |
| `user_id` | Sorguyu soran kullanıcı — **ACL bağlamı eval'in parçasıdır** |
| `question` | Kullanıcının sorusu (doğal dil, Türkçe) |
| `expected_page_keys` | Cevabın kaynağı olması gereken sayfa(lar); en az biri sonuçlarda çıkmalı |
| `forbidden_page_keys` | Sonuçlarda ASLA görünmemesi gereken sayfalar (yetki-sınırı testleri) |
| `category` | `faktuel` · `parafraz` · `kisitli-erisim` · `yetki-siniri` |

## Kategoriler

- **faktuel** — soru, içerikle örtüşen kelimelerle sorulur (lexical isabet ölçer)
- **parafraz** — soru, içerikte GEÇMEYEN kelimelerle sorulur ("evden çalışma" vs
  "uzaktan çalışma"). Semantik boşluğu ölçer; fake embedding ile düşük skor NORMALDİR,
  gerçek embedding modelinin (G-2) kanıtlaması gereken yer burasıdır.
- **kisitli-erisim** — yetkili kullanıcı kısıtlı sayfayı sorar; bulunmalı
- **yetki-siniri** — yetkisiz kullanıcı kısıtlı içeriği sorar; `forbidden_page_keys`
  sonuçlarda çıkarsa eval BAŞARISIZ olur (ACL regresyon bekçisi)

## Sürüm notları

- **v1 (2026-07-06):** 22 soru, 15 sayfalık sentetik korpus üzerinden — harness'i
  çalıştırmak ve baseline almak için. Sorun: bge-m3 ile hit@5=1.00 → **doygun**;
  reranker ve model farkı ölçülemiyor.
- **v2 (2026-07-19):** 45 soru, **40 sayfalık genişletilmiş korpus** üzerinden
  (confusable kümeler — bkz. `scripts/synthetic_corpus.py`). Amaç: G-2 için
  ayırt edici substrat — her sorunun 4-5 makul adayı olduğundan hit@1/MRR
  ayrışır, reranker ve embedding modeli farkı ölçülebilir hale gelir. v1
  soruları korunur (append-only); yeni sorular ağırlıklı parafraz + confusable
  faktüel + aynı-space kısıtlı yetki-sınırı. Korpus değiştiği için v1 sonucu
  (`eval/results/...bge-m3.json`) **tarihsel** kalır, v2 ile kıyaslanmaz — yeni
  baseline v2 üzerinden alınır (matris: `scripts/run_g2_matrix.py`).

  **Gerçek set, pilot space seçilince domain uzmanlarıyla yazılacak** (plan G-3:
  hedef 50-100, Faz 2'de 200+). Set append-only büyür; soru silmek/değiştirmek
  skor kıyaslanabilirliğini bozar (yeni sürüm dosyası açın).

## Çalıştırma

```powershell
python scripts/run_eval.py                 # varsayılan: golden_v1.jsonl, top_k=8
python scripts/run_eval.py --top-k 5
```

Sonuçlar `eval/results/` altına zaman damgalı JSON olarak yazılır — baseline
karşılaştırmaları için commit'lenir.
