# G-2 / ADR-3 — Ölçülebilir embedding + reranker karşılaştırması (GPU)

> **Tarih:** 2026-07-19
> **Kapsam:** PROJE-PLANI.md Faz 0 / G-2 ve ADR-3'ü kapatmak.
> **Durum:** Tasarım — onay bekliyor.

## 1. Amaç ve bağlam

Faz 0 çıkış kriterlerinden yalnızca **ADR-3 (embedding modeli seçimi)** kurumsal
erişim / GPU / K8s beklemeden ilerletilebilir durumda. Bu spec G-2'yi uçtan uca
kapatır: Qwen3-Embedding-0.6B vs bge-m3 karşılaştırması, bge-reranker-v2-m3'ün
katkısının ölçümü, Türkçe token verimliliği — hepsi **GPU üzerinde**.

### 1.1 Çözülen kök problem: doygun eval seti

Mevcut baseline (`eval/results/20260706-171723_BAAI-bge-m3.json`) bge-m3 ile
**hit@5 = 1.00, hit@8 = 1.00** veriyor. 15 sayfa / ~30 chunk'lık korpusta 22 soru
için set **doygun**: rank 3'ün üstünde başlık (headroom) yok.

- Bir reranker top-50 → top-8 yeniden sıralar; her cevap zaten top-5'teyse
  reranker katkısı **tanım gereği ölçülemez**.
- Aynı sebeple Qwen3 vs bge-m3 ikisi de 1.00 alır; model gürültüye göre seçilir.

Bu yüzden ölçümden **önce** ayırt edici bir substrat gerekir (bkz. §5).

### 1.2 Model gerçekleri (config'lerden doğrulandı, 2026-07-19)

| Model | dim | pooling | query/doc | dtype | not |
|---|---|---|---|---|---|
| bge-m3 | 1024 | mean/CLS | **simetrik** | fp32 | mevcut baseline |
| Qwen3-Embedding-0.6B | **1024** | last-token | **asimetrik** | bf16 | query'e instruction prefix |
| bge-reranker-v2-m3 | — | cross-encoder (tek logit) | — | fp32 | XLMRobertaForSequenceClassification |

İki sonuç tüm tasarımı belirler:

1. **Şema değişmez.** Her iki embedding modeli de tam 1024 boyutlu →
   `vector(1024)` ve `EMBEDDINGS_DIM=1024` ikisi için de geçerli. Karşılaştırma
   temiz; re-embed dışında migrasyon yok.
2. **Mevcut arayüz Qwen3 için hatalı.** Qwen3 asimetrik eğitildi: *query*'e
   `"Instruct: Given a web search query, retrieve relevant passages that answer
   the query\nQuery:"` öneki eklenir, *document* çıplak gider. Mevcut
   `embed(texts)` simetrik — ikisine de aynı kodlamayı uygular. Qwen3 bu haliyle
   ölçülürse **sakatlanmış Qwen3** ölçülür ve ADR-3 kararı yanlış çıkar. bge-m3
   simetrik olduğu için etkilenmez — bu farkın gözden kaçması tam da bu yüzden
   kolaydır.

### 1.3 Donanım

RTX 4050 Laptop, 6141 MiB VRAM (~5.1 GB boş), driver 595.97 (CUDA 13.x). Üç model
de ~0.6B parametre. GPU'da **fp16** varsayılanıyla embedding + reranker aynı anda
~2.3 GB'a sığar (fp32 ~4.5 GB — 6 GB'da riskli). Matris koşusu birkaç dakika/geçiş.

**Not:** venv'deki torch şu an `2.12.1+cpu` — GPU'yu kimse bilinçli kapatmadı;
CPU wheel'i kuruldu, `local_st.py` üstüne `device="cpu"` sabitledi ve kısıt
görünmez oldu. `torch==2.12.1+cu130` mevcut (aynı sürüm, CUDA build) → temiz swap.

## 2. Kapsam

**Dahil:** GPU etkinleştirme; asimetrik embedding arayüzü; CrossEncoder reranker
+ factory + config; korpus genişletme (ayırt edici, confusable kümeler) +
golden_v2; matris koşucu + rapor; Türkçe token verimliliği; birim testleri;
PROJE-PLANI.md / ADR-3 güncellemesi.

**Hariç (bilinçli):** vLLM/openai embedding üretim yolu (arayüz hazır, ölçüm
yerelde); reranker HTTP servis istemcisi (Faz 1); gerçek Confluence içeriği (G-0);
CI eval kapısı (Faz 2). Korpus içeriği sentetik-ama-gerçekçi; kullanıcı kararı:
içerik gözden geçirilmeyecek, metriklerle değerlendirilecek.

## 3. Bileşen tasarımı

### 3.1 GPU etkinleştirme

- venv torch swap: `2.12.1+cpu` → `2.12.1+cu130` (PyTorch cu130 index'inden).
  Sürüm aynı → bağımlılık oynamaz. Kurulum implementasyon planında adım olarak.
- `config.py`: yeni `embeddings_device: str = "auto"` (auto|cuda|cpu) ve
  `embeddings_dtype: str = "auto"` (auto|float16|float32|bfloat16). `auto` →
  cuda varsa cuda+float16, yoksa cpu+float32.
- `local_st.py`: sabit `device="cpu"` yerine çözümlenen device/dtype;
  `SentenceTransformer(model_name, device=..., model_kwargs={"torch_dtype": ...})`.
  Seçilen device stderr'e loglanır (kısıt bir daha görünmez olmasın).

### 3.2 Asimetrik embedding arayüzü

`EmbeddingProvider` (base.py):

```python
class EmbeddingProvider(ABC):
    name: str
    dim: int
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_documents(self, texts): return await self.embed(texts)
    async def embed_query(self, texts):     return await self.embed(texts)
    async def close(self): ...
```

- `fake`, `openai_compat`: değişmez — simetrik varsayılanları miras alır.
  (`test_fake_embeddings.py` `embed()`'i çağırmaya devam eder, kırılmaz.)
- `LocalSTEmbeddings`: sentence-transformers'ın **native `prompt_name`** yolu.
  Model kendi `prompts` sözlüğünü taşır (`config_sentence_transformers.json`).
  Qwen3 `{query: "Instruct…", document: ""}` taşır → `encode(prompt_name="query")`
  prefix'i otomatik ekler; bge-m3'te prompts yok → düz encode. **Model başına
  sabit kodlama yok** — ikisi de yapı gereği doğru.

  ```python
  def _encode(self, texts, prompt_name):
      use = prompt_name if prompt_name in (self._model.prompts or {}) else None
      vectors = self._model.encode(texts, normalize_embeddings=True,
                                   batch_size=..., prompt_name=use)
      ... # dim doğrulaması aynen korunur
  ```

- Çağıran taraf yönlendirmesi: `indexer.py` → `embed_documents`;
  `service.py` → `embed_query`. (Tek satırlık değişiklikler; anlamsal olarak
  zaten doğru olan ayrım açık hale gelir.)

### 3.3 Reranker

- `rerank.py`: mevcut `Reranker` ABC + `NoopReranker` korunur. Yeni
  `CrossEncoderReranker(Reranker)` — ağır import (sentence-transformers) lazy,
  embeddings deseninin aynısı. `rerank(query, results, top_k)`:
  `(query, r["content"])` çiftleri → `CrossEncoder.predict(...)` → skorları
  `r["debug"]["rerank_score"]`'a yaz, azalan sırala, `top_k` döndür.
  Device/dtype §3.1'deki çözümü paylaşır.
- Yeni `create_reranker(settings)` factory (`create_embeddings` gibi):
  `reranker_provider` = `noop` | `local`. `local` → `CrossEncoderReranker(
  settings.reranker_model or "BAAI/bge-reranker-v2-m3", device, dtype)`.
- `config.py`: `reranker_provider: str = "noop"`, `reranker_model: str = ""`.
- `service.py._shape`: `rerank_score` varsa debug'a ekle (yoksa dokunma).
  Sıralama zaten reranker'dan gelir; eval sayfa-sırası ölçer.
- `api/main.py`, `scripts/run_eval.py`, `scripts/dev_query.py` → `NoopReranker()`
  yerine `create_reranker(settings)` kullanır.
- `scripts/acl_leak_test.py` → **NoopReranker sabit kalır**: erişim kümesini test
  eder, sıralamayı değil; reranker ACL'i etkilemez ve gereksiz model yükü
  getirmemeli (test hızlı/odaklı kalsın).

### 3.4 Ayırt edici korpus

- `synthetic_corpus.py` **genişletilir, mevcut 15 sayfa DEĞİŞTİRİLMEZ** (mevcut
  page_key'ler geçerli kalır; golden_v1 çözülebilir kalır). Hedef ~40 sayfa,
  **confusable kümeler** halinde — ayırt ediciliği sayfa sayısı değil
  karıştırılabilirlik yaratır:

  | Küme (space) | Sayfalar (mevcut + yeni) |
  |---|---|
  | İzin (IK) | yıllık-izin* + hastalık-izni, doğum/ebeveyn-izni, ücretsiz-izin, resmi-tatil-takvimi |
  | Erişim/uzaktan (IK+ENG) | uzaktan-çalışma* + ekipman-zimmet, ofis-kullanım, VPN* |
  | Masraf/satınalma (FIN) | masraf* + satınalma* + seyahat-harcırah, kurumsal-kart, fatura-kesim |
  | Güvenlik (ENG) | güvenlik-açığı*(kısıtlı) + olay-müdahale* + parola-politikası, veri-sınıflandırma(kısıtlı) |
  | Dağıtım/eng (ENG) | dağıtım* + kod-inceleme* + sürümleme, test-stratejisi, nöbet-eskalasyon |
  | Ücret/İK-yönetim (IK) | maaş-bantları*(kısıtlı) + işten-çıkış*(kısıtlı) + prim-politikası(kısıtlı) |

  `*` = mevcut. Yeni kısıtlı sayfalar kümelere eklenir → yetki-sınırı testi de
  zorlaşır (forbidden sayfanın etrafında daha çok benzer içerik).

- Yeni sayfalar mevcut GROUPS/SPACE_VIEWERS/restricted_to semantiğine uyar;
  `expected_allowed_pages` / `expected_allowed_spaces` hesabı otomatik kapsar
  (yeni grup gerekmez; gerekirse eklenir ve testle sabitlenir).

- `eval/golden/golden_v2.jsonl` (~45 soru): v1 soruları korunur (append-only) +
  küme-hedefli faktüel/parafraz/yetki-sınırı soruları. Ağırlık ayırt edici
  kategorilerde (parafraz, confusable-küme faktüel). v1 sonucu git'te tarihsel
  artefakt olarak kalır, **açıkça** yeni korpusla geçersizleşir (README'nin
  "yeni sürüm dosyası açın" yolu). golden README'ye v2 sürüm notu eklenir.

### 3.5 Matris koşucu (ADR-3'ü kapatan çıktı)

- `seed_synthetic.py`'den **içerik-only** `index_corpus(pool, embedder)` ayrıştırılır
  (FGA bootstrap ayrı kalır — FGA tuple'ları modele bağlı değil, yalnız embedding
  yeniden yazılır). `seed_synthetic.main()` bunu çağırır (davranış aynı).
- `scripts/run_g2_matrix.py`:
  1. FGA seed'i mevcut mu kontrol (yoksa kullanıcıyı `seed_synthetic`'e yönlendir
     ya da bir kez bootstrap et).
  2. Her embedding modeli {bge-m3, Qwen3} için: embedder kur → `index_corpus`
     (2 re-index geçişi toplam).
  3. Her reranker {noop, bge-reranker-v2-m3} için: golden_v2 üzerinde eval çalıştır
     (reranker query-time → re-index gerekmez), metrik topla.
  4. Çıktı: `eval/results/<stamp>_g2_matrix.json` + markdown rapor
     `eval/results/g2-report.md` — karşılaştırma tablosu (MRR, hit@1/3/5, parafraz
     hit@5, latency p95, ACL ihlali) + ADR-3 önerisi.
- run_eval'daki skorlama mantığı paylaşılır: ortak fonksiyona ayrıştırılır
  (`score_run(service, items, top_k) -> metrics`), hem `run_eval.py` hem matris
  kullanır (kopya yok).

### 3.6 Türkçe token verimliliği

- `scripts/token_efficiency.py`: her modelin tokenizer'ını korpus üzerinde koştur;
  tokens/kelime ve tokens/karakter raporla (bge-m3 XLM-R 250k SentencePiece vs
  Qwen 151k). Bağlam bütçesi + maliyet planına girdi. `transformers` tokenizer'ı
  yeterli (model ağırlığı gerekmez → hızlı). Çıktı konsol + rapora eklenir.

### 3.7 Testler ve kapanış

Birim testleri (GPU/indirme YOK):
- `embed_query`/`embed_documents` varsayılanları simetrik sağlayıcılarda `embed`'e
  eşit (fake ile).
- `CrossEncoderReranker` sıralaması: enjekte edilen sahte skorlayıcı ile
  (gerçek model indirmeden) azalan sıralama + top_k + rerank_score yazımı.
- Korpus tutarlılığı: yeni distractor'lar `expected_allowed_pages` beklentilerini
  bozmuyor; yeni kısıtlı sayfalar doğru grupla eşleşiyor (mevcut
  `test_synthetic_expectations.py` desenini genişlet).
- `create_reranker` factory: noop/local seçimi, bilinmeyen provider hatası.

Kapanış:
- `PROJE-PLANI.md`: G-2 `[x]`, ADR-3 ✅ (seçilen model + sayılar), Faz 0 çıkış
  kriteri "Embedding modeli seçildi" işaretlenir. Karar rapordan beslenir.

## 4. Veri akışı

```
INDEX (model M):  corpus → chunk → embed_documents(M) → chunks.embedding, embedding_model=M
QUERY:            q → embed_query(M) ─┐
                                      ├→ hybrid_search (ACL pre-filter, RRF) → top-50 aday
                  q ──────────────────┘        │
                                       reranker.rerank(q, adaylar, top_k) → top-k
                                               │
                                        RetrievalService.retrieve → citation'lı sonuç
MATRIS:  for M in {bge-m3, Qwen3}: index_corpus(M);
             for R in {noop, bge-reranker-v2-m3}: score_run(golden_v2) → hücre
         → g2_matrix.json + g2-report.md
```

## 5. Hata ve sınır durumları

- **VRAM:** GPU'da fp16 varsayılan → embedding+reranker ~2.3 GB. OOM olursa
  `embeddings_dtype=float16` zaten aktif; fallback CPU (device=cpu) configten.
- **Model prompts yokluğu:** `prompt_name` model.prompts'ta yoksa `None`'a düşer
  (bge-m3 yolu) — hata değil, doğru davranış.
- **dim uyumsuzluğu:** mevcut doğrulama korunur (1024 değilse ValueError) — yanlış
  model erken yakalanır.
- **FGA seed eksik:** matris koşucu net hata/yönlendirme verir (sessiz boş sonuç
  yok — fail-closed ACL zaten boş space'te 0 satır döner).
- **ACL regresyonu:** matrisin her hücresi golden_v2'nin yetki-sınırı sorularını
  içerir; ihlal → o hücre için eval exit 1 (mevcut davranış korunur).

## 6. Kabul kriterleri

- [ ] `torch.cuda.is_available()` True; `local_st` ve reranker GPU'da koşar (log doğrular).
- [ ] Qwen3 query'leri instruction prefix ile embed'lenir (prompt_name yolu testli/doğrulanmış).
- [ ] golden_v2 üzerinde bge-m3 hit@5 < 1.00 (set artık ayırt edici — headroom var).
- [ ] Matris 4 hücre üretir; `g2-report.md` karşılaştırma tablosu + ADR-3 önerisi içerir.
- [ ] Tüm hücrelerde ACL ihlali = 0.
- [ ] Token verimliliği raporu iki model için tokens/kelime verir.
- [ ] Birim testleri GPU/indirme olmadan geçer (`pytest`).
- [ ] PROJE-PLANI.md G-2/ADR-3 kapanışı güncellenir.

## 7. Dosya değişiklikleri (özet)

| Dosya | Değişiklik |
|---|---|
| venv torch | cpu → cu130 wheel (plan adımı) |
| `src/ragplatform/config.py` | +embeddings_device, +embeddings_dtype, +reranker_provider, +reranker_model |
| `src/ragplatform/embeddings/base.py` | +embed_query/embed_documents (simetrik varsayılan) |
| `src/ragplatform/embeddings/local_st.py` | device/dtype çözümü + prompt_name yönlendirme |
| `src/ragplatform/ingestion/indexer.py` | embed → embed_documents |
| `src/ragplatform/retrieval/service.py` | embed → embed_query; _shape rerank_score |
| `src/ragplatform/retrieval/rerank.py` | +CrossEncoderReranker +create_reranker |
| `src/ragplatform/api/main.py`, `scripts/{run_eval,dev_query}.py` | create_reranker kullan (acl_leak_test noop sabit) |
| `scripts/synthetic_corpus.py` | +~25 sayfa (confusable kümeler), mevcutlar sabit |
| `scripts/seed_synthetic.py` | index_corpus ayrıştır |
| `scripts/run_g2_matrix.py` | YENİ — matris + rapor |
| `scripts/token_efficiency.py` | YENİ — tokens/kelime |
| `eval/golden/golden_v2.jsonl` | YENİ — ~45 soru |
| `eval/golden/README.md` | v2 sürüm notu |
| `tests/` | +reranker, +embed arayüz, +korpus tutarlılık |
| `PROJE-PLANI.md` | G-2/ADR-3 kapanış |
| `pyproject.toml` | `local` extra: sentence-transformers zaten var; not düşülebilir |
