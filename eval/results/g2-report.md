# G-2 / ADR-3 — Embedding + Reranker Karşılaştırma Raporu

> **Üretim:** `scripts/run_g2_matrix.py` · 2026-07-20T08:12:35+00:00  
> **Golden set:** `golden_tr_v1.jsonl` · **Korpus:** 27 sayfa (confusable kümeler) · **top_k:** 8 · **Donanım:** yerel GPU (fp16)

---

## 🎯 Karar (ADR-3)

> **Seçilen embedding modeli: `bge-m3`.** Reranker (`bge-reranker-v2-m3`): **duruma göre** — kalite artıyor ama p95 6.3× yükseliyor; gecikmeye duyarlı kullanımda kapalı bırakılabilir.

`bge-m3`, rerank'siz izole kalitede (MRR **0.974**, hit@1 **0.949**) diğer adayı geçti; reranker ile MRR **0.987**'e çıkıyor. Türkçe token verimi ve latency'de de önde (aşağıda). Gerekçelerin tamamı §Yorum'da.

## Yöntem

**Neden bu ölçüm?** İlk golden set (15 sayfa, 22 soru) bge-m3 ile hit@5=1.00 veriyordu — *doygun*. Her cevap zaten ilk 5'te olunca reranker top-50→top-8 yeniden sıralaması ve modeller arası fark **tanım gereği ölçülemez**. Bu yüzden önce ayırt edici bir substrat üretildi:

- **Korpus:** 27 doküman. Sorgu başına birden çok makul aday bulunması hedeflenir → hit@1 ve MRR ayrışır.
- **Golden set:** `golden_tr_v1.jsonl`: faktüel · parafraz (semantik boşluk) · kısıtlı-erişim · yetki-sınırı (aynı-space kısıtlı → sıkı ACL testi).
- **Matris:** {`bge-m3`, `qwen3-0.6b`} × {noop, `bge-reranker-v2-m3`}. Embedding değişimi re-index gerektirir (vektörler modele bağlı); reranker query-time.
- **ACL:** her hücre yetki-sınırı sorularını içerir; forbidden sayfa dönerse eval düşer.

## Sonuç matrisi

| embedding | reranker | MRR | hit@1 | hit@3 | hit@5 | parafraz@5 | p95 (ms) | ACL |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `bge-m3` | noop | **0.974** | 0.949 | 1.000 | 1.000 | 1.000 | 107.2 | 0 |
| `bge-m3` ⭐ | bge-reranker-v2-m3 | **0.987** | 0.974 | 1.000 | 1.000 | 1.000 | 678.1 | 0 |
| `qwen3-0.6b` | noop | **0.932** | 0.872 | 1.000 | 1.000 | 1.000 | 179.5 | 0 |
| `qwen3-0.6b` | bge-reranker-v2-m3 | **0.987** | 0.974 | 1.000 | 1.000 | 1.000 | 697.0 | 0 |

⭐ = seçilen yapılandırma. MRR = ortalama karşılıklı sıra (sayfa bazında).

> ⚠️ hit@5 tüm hücrelerde 1.000 — set k=5'te **doygun**; ayrım yalnız MRR ve hit@1'den geliyor. Daha ince ayrım için sete daha zor/karıştırıcı sorular eklenmeli.

## Kategori bazında hit@5

| embedding | reranker | faktuel | kisitli-erisim | parafraz |
|---|---|:--:|:--:|:--:|
| `bge-m3` | noop | 1.000 | 1.000 | 1.000 |
| `bge-m3` | bge-reranker-v2-m3 | 1.000 | 1.000 | 1.000 |
| `qwen3-0.6b` | noop | 1.000 | 1.000 | 1.000 |
| `qwen3-0.6b` | bge-reranker-v2-m3 | 1.000 | 1.000 | 1.000 |

## Yorum

### Embedding: `bge-m3` vs `qwen3-0.6b`

Rerank'siz (embedding kalitesi izole): `bge-m3` MRR **0.974** / hit@1 **0.949**.
- `qwen3-0.6b`: MRR 0.932 / hit@1 0.872 (parafraz@5 1.000).

`bge-m3` daha yüksek hit@1 veriyor — confusable kümede doğru sayfayı ilk sıraya koyma yeteneği belirleyici. Parafraz (semantik boşluk) her iki modelde yakın.

### Reranker (`bge-reranker-v2-m3`) etkisi

`bge-m3` üzerinde: MRR 0.974 → **0.987** (Δ+0.013), hit@1 0.949 → **0.974**, parafraz@5 1.000 → **1.000**. Latency bedeli: p95 107.2 → 678.1ms (hedef <300ms içinde). Cross-encoder, RRF'in geniş recall'ını hassaslaştırıyor ve embedding'ler arası farkı kapatıyor → **duruma göre** — kalite artıyor ama p95 6.3× yükseliyor; gecikmeye duyarlı kullanımda kapalı bırakılabilir.

### Türkçe token verimliliği

Korpus: 39692 kelime, 320886 karakter.

| model | tokens | tok/kelime | tok/karakter | vocab |
|---|:--:|:--:|:--:|:--:|
| `BAAI/bge-m3` | 71093 | **1.791** | 0.2216 | 250002 |
| `Qwen/Qwen3-Embedding-0.6B` | 102745 | **2.589** | 0.3202 | 151643 |

`bge-m3` Türkçe'yi daha verimli parçalıyor: `Qwen3-Embedding-0.6B` aynı metin için ~%45 fazla token üretiyor → daha küçük etkin bağlam + daha yüksek GPU/API maliyeti. Türkçe ağırlıklı içerikte bu doğrudan bir seçim kriteri.

### Latency

Tüm hücreler retrieval p95 hedefinin (<1s; bu PoC'de <300ms) altında. `bge-m3`: 107.2ms/678.1ms · `qwen3-0.6b`: 179.5ms/697.0ms (noop/rerank).

### ACL

Matris genelinde toplam yetki-sınırı ihlali: **0** (✅ temiz). 40-sayfalık korpusta aynı-space kısıtlı yetki-sınırı testleri (kullanıcı space'i görüyor ama kısıtlı sayfayı görmemeli) dahil sızıntı yok.

## Sınırlar ve sıradaki adım

- **Sentetik içerik.** Karar sentetik (ama gerçekçi) Türkçe korpus üzerinde. Plan, gerçek ~%90 Türkçe pilot içeriği (G-0) ile yeniden doğrulamayı öngörüyor — matris tek komutla koşar.
- **0.6B karşılaştırıldı.** Daha büyük Qwen3-Embedding (4B/8B) `bge-m3`'i geçebilir; GPU serving hazır olunca değerlendirilebilir.
- **In-process reranker.** Üretimde ayrı vLLM/servis havuzuna taşınacak (Faz 1).

## Yeniden üretim

```powershell
python scripts/run_g2_matrix.py           # tam matris (GPU) + rapor
python scripts/g2_report.py <matris.json> # kayıtlı JSON'dan raporu yeniden render et
python scripts/token_efficiency.py        # yalnız token verimliliği
```
