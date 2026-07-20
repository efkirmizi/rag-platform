# ACL-Native RAG — Proje Planı

> **Son güncelleme:** 2026-07-20
> **Ne bu:** Yetki-farkındalıklı (ACL-native) retrieval'ın **açık kaynak referans
> uygulaması**. Kişisel bir projedir — bir kurum dağıtımı değildir.
> **Durum:** ACL PoC ✅ (sızıntı 0/480) · eval harness ✅ · ADR-3 ✅ bge-m3 ·
> ölçek doğrulaması ✅ (gizli recall riski bulundu ve kapatıldı) · üretim
> (generation) ✅ opsiyonel · klasör + Docling ingest ✅ · gerçek Türkçe korpus ✅
> Kod: `src/ragplatform/` · kurulum: `README.md` · ölçümler: `eval/results/`

> [!NOTE]
> **Kapsam değişikliği (2026-07-20).** Bu doküman başlangıçta bir *kurum içi
> dağıtım planı* olarak yazılmıştı: Confluence connector'ı, pilot kullanıcı
> grubu, K8s/GPU havuzları, LiteLLM gateway, control plane, compliance onayı…
> Böyle bir kurumsal bağlam **yok** ve olmayacak. Proje kişisel/açık kaynak
> olarak sürüyor.
>
> Gerçekçi yol haritası §4'tedir. Özgün kurumsal plan silinmedi — mimari düşünce
> değerli olduğu için **[Ek A](#ek-a--kurumsal-dağıtım-planı-arşiv)**'da
> arşivlendi. Ek A **taahhüt değildir**; bir kurum bağlamı doğarsa referans olsun
> diye durur.

---

## 1. Vizyon ve Kapsam

**Retrieval, kullanıcının doküman izinlerine sorgu anında ve fail-closed saygı
göstermeli.** RAG projelerinin çoğu yetkilendirmeyi ya sonradan filtreleyerek ya
da hiç ele almayarak geçiştirir; gerçek bir doküman kümesinde (İK'nın maaş
sayfasıyla herkese açık el kitabı yan yana) bu kırılır.

Bu proje bunu doğru yapmanın çalışan, ölçülmüş ve kopyalanabilir bir örneğini
sunar: OpenFGA erişim seti → SQL'de pre-filter → hybrid arama → reranker →
citation. Türkçe-öncelikli, çünkü Türkçe retrieval (stemming, token verimliliği,
model seçimi) yeterince ele alınmamış bir alan.

**Hedef kitle:** kendi dokümanlarını yetki-farkındalıklı biçimde aramak isteyen
geliştiriciler; ve ACL'li RAG'ın nasıl kurulduğuna bakmak isteyenler.

**Kapsam dışı:** fine-tuning, ses/görüntü, internet araması, otonom yazma
aksiyonları. Ayrıca kurumsal altyapı katmanı (Ek A) — tek kişilik bir projenin
sürdüremeyeceği yük.

---

## 2. Hedef Mimari

Orijinal mimarinin üzerine eklenenler: **Retrieval kalite hattı (hybrid + reranker), Platform API, güvenlik katmanı (DLP/guardrail/audit), eval kapısı, kuyruk tabanlı ingestion, Redis cache.**

```
┌─────────────────────────────────────────────────────────────────────┐
│  TÜKETİCİLER:  LibreChat (ince UI)  │  Teams/Slack  │  İç Uygulamalar│
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│  PLATFORM API (FastAPI)                                             │
│  authN (OIDC) · rate limit · audit · tenant/agent yönlendirme       │
└───────┬──────────────────────────────────────────────┬──────────────┘
        │                                              │
┌───────▼────────────────────────┐   ┌─────────────────▼──────────────┐
│  AI CONTROL PLANE              │   │  GÜVENLİK KATMANI              │
│  Agent Registry                │   │  Girdi guardrail               │
│  KB Registry                   │   │  Çıktı guardrail + DLP maske   │
│  MCP Tool Registry (risk+onay) │   │  Prompt injection savunması    │
│  Policy/ACL binding            │   │  Audit log (soru/retrieval/    │
│  Prompt + Flow versiyonları    │   │  tool çağrısı — değiştirilemez)│
└───────┬────────────────────────┘   └────────────────────────────────┘
        │
┌───────▼───────────────┐    ┌───────────────────────────────────────┐
│  AGENT RUNTIME        │    │  RETRIEVAL SERVICE (custom)           │
│  Basit RAG: düz hat   │◄──►│  Query rewrite/multi-query            │
│  Karmaşık: LangGraph  │    │  ACL pre-filter (OpenFGA erişim seti) │
│  MCP tools (onaylı)   │    │  Hybrid: pgvector HNSW + PG FTS (RRF) │
└───────┬───────────────┘    │  Reranker (bge-reranker-v2-m3)        │
        │                    │  Citation üretimi                     │
        │                    └───────────────┬───────────────────────┘
┌───────▼────────────────────────┐           │
│  LiteLLM AI GATEWAY            │   ┌───────▼───────────────────────┐
│  agent_id/user_id/trace_id     │   │  INGESTION (Argo Workflows)   │
│  model routing · fallback      │   │  Connector → Docling parse →  │
│  bütçe/rate limit · maliyet    │   │  chunk → embed → index        │
└───────┬────────────────────────┘   │  Incremental sync + idempotent│
        │                            │  PII/DLP tarama · izin sync   │
┌───────▼────────────────────────┐   └───────┬───────────────────────┘
│  MODEL SERVING (vLLM)          │           │
│  Generation: Qwen3             │   ┌───────▼───────────────────────┐
│  Embedding: ayrı havuz         │   │  KAYNAKLAR                    │
│  Reranker: ayrı havuz          │   │  Confluence · PDF/DOCX/HTML   │
└────────────────────────────────┘   │  (object storage'da ham kopya)│
                                     └───────────────────────────────┘

YATAY KATMANLAR
├─ Observability : Langfuse (trace+eval+prompt ver.+feedback merkezi)
│                  + Prometheus/Grafana + OpenTelemetry
├─ AuthN/AuthZ   : OIDC/LDAP (kimlik) + OpenFGA (ReBAC yetki)
├─ Cache         : Redis (exact-match v1 → semantic cache v2)
├─ Eval          : Golden set + offline eval + CI regresyon kapısı
└─ Storage       : PostgreSQL + pgvector · object storage · Redis
```

### Bileşen seçimleri ve gerekçeler

| Katman | Seçim | Gerekçe |
|---|---|---|
| Chat UI | **LibreChat (ince)** | Ağır logic dışarıda; UI değiştirilebilir kalır. Platform API'nin sadece bir tüketicisi. |
| RAG servisi | **Custom (RAGFlow değil)** | OpenFGA ile ACL pre-filter, hybrid+rerank hattı ve izin senkronu RAGFlow'a sağlıklı entegre edilemez. Kontrol bizde olmalı. Docling'i parse için kullanıyoruz, RAGFlow'un bütününü değil. |
| Vector store | **pgvector** (çıkış eşiği tanımlı) | Operasyonel basitlik, ACID, metadata filtre + FTS aynı DB'de. Çıkış eşiği: §3 ADR-2. |
| Hybrid search | **pgvector HNSW + Postgres FTS (`turkish` config + `unaccent`), RRF füzyonu** | Hata kodu/kısaltma/ürün adı gibi lexical sorgular dense aramada kaçar. Türkçe'nin eklemeli yapısı için stemming şart. Tek DB'de çözülüyor. |
| Reranker | **bge-reranker-v2-m3** | Çok dilli (Türkçe dahil), açık model, on-prem servis edilebilir. En yüksek kalite/efor kaldıracı. |
| Embedding | **Aday: Qwen3-Embedding; alternatif: bge-m3** | İçerik ağırlıklı Türkçe → **Türkçe skoru belirleyici kriter.** Faz 0'da ~%90 Türkçe test setiyle ölçülüp seçilecek (ADR-3). Versiyonlanır, re-embed runbook'u ile. |
| Generation | **vLLM + Qwen3** | Veri egemenliği (on-prem), mevcut tercih korunuyor. |
| Orkestrasyon | **Basit RAG = düz pipeline; LangGraph sadece stateful/onaylı flow'lar** | Orijinal madde 5 aynen korunuyor — doğru karar. |
| Gateway | **LiteLLM** | Tek kapı: maliyet dağıtımı, routing, fallback, bütçe. Metadata standardı zorunlu (ADR-5). |
| Ingestion | **Argo Workflows + outbox/kuyruk deseni** | K8s-native, adım bazlı retry. Kafka ancak hacim gerektirirse (ADR-6). |
| AuthZ | **OpenFGA, materialize edilmiş erişim seti ile pre-filter** | Post-filter dar yetkili kullanıcıda boş sonuç verir; sorgu anında FGA çağrısı ölçeklenmez. Desen: §4 Faz 0 / G-1. |
| Observability | **Langfuse + Prometheus + OTel** | Korunuyor. Langfuse = prompt versiyon + eval + feedback merkezi. |
| PII/DLP | **Microsoft Presidio + custom tanıyıcılar** | Açık kaynak, Türkçe pattern'ler eklenebilir (TCKN vb.). |
| Cache | **Redis: v1 exact-match, v2 semantic** | Semantic cache yanlış pozitif riski taşır; önce basitle başla. |

---

## 3. Kilit Mimari Kararlar (ADR)

| # | Karar | Durum | Not |
|---|---|---|---|
| ADR-1 | RAG servisi custom yazılacak, RAGFlow kullanılmayacak | ✅ Karar | Gerekçe: ACL entegrasyonu + kontrol. Docling parse için kullanılır. |
| ADR-2 | pgvector ile başla; **çıkış eşiği:** >20M chunk VEYA p95 filtreli ANN >150ms VEYA index build >4saat → Qdrant migrasyonu değerlendir | ✅ Karar · ölçüldü (2026-07-20) | Migrasyon hedefi Qdrant. **Ölçüm (100k chunk):** planlayıcı filtre varken HNSW'yi kullanmıyor, izinli alt kümeyi seq scan ediyor → recall 1.000 ama maliyet *görünür satır* sayısıyla doğrusal; 150ms eşiği ~25k görünür chunk'ta geliyor (toplam korpus değil, **kullanıcı başına görünürlük** eşiği). Index kullanıldığında pgvector varsayılanı `iterative_scan=off` recall'ı 0.367'ye düşürüyor → `relaxed_order` uygulandı (`db.py`). Denormalizasyon (`space_key`'i `chunks`'a taşımak) **denendi ve reddedildi**: %58-102 daha yavaş — JOIN aslında bir optimizasyon (küçük `pages` tablosu filtrelenip tamsayı hash join'e dönüşüyor; denormalize hâlde satır başına `text[]` araması yapılıyor). Mevcut şema korunuyor. Rapor: `eval/results/scale-report.md` |
| ADR-3 | Embedding modeli seçimi: **bge-m3** (reranker: bge-reranker-v2-m3 açık) | ✅ Karar (2026-07-19) | Qwen3-Embedding-0.6B vs bge-m3, golden_v2 (40-sayfa confusable, %100 TR) + GPU ile ölçüldü. bge-m3 rerank'siz kalite (MRR 0.937 vs 0.896), Türkçe token verimi (1.76 vs 2.62 tok/kelime → ~%49 daha az bağlam/maliyet) ve latency'de üstün; reranker ile ikisi de tavana ulaşıyor. Not: 0.6B Qwen3 karşılaştırıldı; daha büyük Qwen3 (4B/8B) gerçek pilotta yeniden değerlendirilebilir. Rapor: `eval/results/g2-report.md`. |
| ADR-4 | ACL deseni: OpenFGA `ListObjects` → erişim seti → pgvector sorgusunda metadata pre-filter | ✅ Karar | Faz 0 PoC ile doğrulanacak; başarısızsa mimari revize edilir. |
| ADR-5 | Gateway metadata standardı: `agent_id, user_id, trace_id, kb_ids[], prompt_version, flow_version` her LLM çağrısında zorunlu | ✅ Karar | LiteLLM middleware'de enforce edilir; eksikse çağrı reddedilir. |
| ADR-6 | Ingestion: Argo Workflows + Postgres outbox; Kafka yalnız >100K doküman/gün olursa | ✅ Karar | Erken Kafka = gereksiz operasyonel yük. |
| ADR-7 | Eval kapısı: golden set regresyonu geçmeyen prompt/flow versiyonu prod'a çıkamaz | ✅ Karar | CI pipeline'da zorunlu adım. |
| ADR-8 | Retrieval içeriği "untrusted" işaretlenir; tool çağrısı tetikleyemez | ✅ Karar | Indirect prompt injection savunmasının temeli. |
| ADR-9 | İzin tazeliği hedefi: kaynak sistemde iptal edilen erişim ≤15 dk içinde retrieval'a yansır | ⬜ Onay bekliyor | Compliance ekibiyle SLA netleştirilecek. |

---

## 4. Yol Haritası (kişisel proje)

Tarih yok, faz yok, "çıkış kriteri" yok — tek kişilik bir projede bunlar kurgu
olur. Sıra, değer/efor oranına göre.

### Yapıldı (ölçümüyle birlikte)

- [x] **ACL-filtered hybrid retrieval** — OpenFGA erişim seti → SQL pre-filter,
      fail-closed. Sızıntı **0/480**. `scripts/acl_leak_test.py`
- [x] **Eval harness + golden setler** — hit@k, MRR, yetki-sınırı, latency;
      kalite eşikleriyle CI kapısı. `scripts/run_eval.py`
- [x] **ADR-3: embedding + reranker seçimi** — bge-m3 (Qwen3-0.6B'ye karşı
      ölçüldü), bge-reranker-v2-m3 katkısı +0.032 MRR. `eval/results/g2-report.md`
- [x] **Ölçek doğrulaması** — 100k chunk. Gizli bir recall riski bulundu
      (`hnsw.iterative_scan=off` ile filtreli aramada recall 0.367) ve kapatıldı;
      denormalizasyon denendi ve reddedildi. `eval/results/scale-report.md`
- [x] **Üretim (generation)** — `/v1/answer`, citation doğrulamalı, ADR-8
      çerçevelemesiyle; opsiyonel ve varsayılan kapalı
- [x] **Kendi dokümanını getir** — klasör connector'ı (markdown + Docling ile
      PDF/DOCX/HTML), `path_rules` ile dizin bazlı izin
- [x] **Gerçek Türkçe korpus** — sentetik sayfalar chunking'i ölçemeyecek kadar
      kısaydı; Vikipedi'den 27 uzun doküman + 45 soruluk golden set
      (`scripts/fetch_corpus.py`, `eval/golden/golden_tr_v1.jsonl`)

### Sırada

- [ ] **Chunking parametrelerini gerçek metinle karara bağla** — sentetik
      korpusta deney boştu (parametreler hiç devreye girmiyordu); gerçek korpusla
      tekrar. `scripts/run_chunking_matrix.py --docs data/tr-corpus`
- [ ] **ADR-3'ü gerçek metinle doğrula** — embedding/reranker karşılaştırması
      sentetik içerikte yapılmıştı; aynı matrisi gerçek korpusta koştur
- [ ] **Demo'yu gerçek embedding'le çalıştır** — şu an demo `fake` embedding
      kullanıyor, yani ziyaretçi anlamsız semantik sonuç görüyor
- [ ] **Artımlı senkron** — `content_hash` var ama kullanılmıyor; değişmeyen
      dokümanı yeniden embed etmemek (klasör connector'ı için anlamlı)

### Belki (kanıt gerektirir)

- [ ] Query rewrite / multi-query — eval ile faydası gösterilirse
- [ ] Basit web arayüzü — yetki-farkındalıklı retrieval'ı tarayıcıda göstermek
- [ ] Yeni kaynaklar (Notion/Obsidian/dosya paylaşımı) — klasör connector'ı deseni üstünden
- [ ] Semantic cache — önce exact-match'in isabet oranı ölçülmeli

### Bilinçli olarak YAPILMAYACAK

K8s/GPU havuzları, Argo Workflows, LiteLLM gateway, Langfuse, control plane,
agent/MCP registry, chargeback, DR tatbikatı, compliance süreçleri. Hepsi bir
kurum bağlamında doğru; tek kişilik bir projede sürdürülemez yük. Gerekçeleriyle
birlikte [Ek A](#ek-a--kurumsal-dağıtım-planı-arşiv)'da duruyor.

---

## 5. Ölçülmüş Bulgular (kanıt dizini)

Bu projede "daha iyi" iddiaları ölçümle desteklenir. Raporlar:

| Konu | Sonuç | Rapor |
|---|---|---|
| Embedding + reranker (ADR-3) | bge-m3 seçildi; reranker +0.032 MRR | `eval/results/g2-report.md` |
| Ölçekte ACL-filtreli ANN | Recall riski bulundu+kapatıldı; denormalizasyon reddedildi | `eval/results/scale-report.md` |
| Chunking parametreleri | Sentetik korpusta **sonuçsuz** (deney boştu) — gerçek korpusla tekrar ediliyor | `eval/results/chunking-matrix.json` |
| Türkçe token verimliliği | bge-m3 1.76 vs Qwen3 2.62 tok/kelime | `eval/results/g2-report.md` |

**Ölçüm dürüstlüğü notu:** golden sorular korpus bilinerek yazıldı; sayılar
*göreli* karşılaştırma (model A vs B) için geçerli, mutlak kalite kanıtı değil.
Ölçüm harness'ları birkaç kez yanlış sayı üretip düzeltildi (yinelenen vektörler,
boş chunking deneyi) — bu yüzden artık kendi geçerliliklerini denetliyorlar.

---

## Ek A — Kurumsal Dağıtım Planı (arşiv)

> [!WARNING]
> **Aşağıdakiler PLANLANMIYOR.** Bu bölüm, projenin başlangıçtaki kurum içi
> dağıtım tasarımıdır. Böyle bir bağlam bulunmadığı için hiçbiri yapılmayacak.
> Mimari muhakeme (neden pre-filter, neden custom RAG servisi, neden bu eşikler)
> değerli olduğu ve bir gün bir kurum bağlamı doğarsa başlangıç noktası olacağı
> için silinmedi.
>
> Aşağıdaki tarihler, "faz çıkış kriterleri", pilot grup ve ekip varsayımları
> tarihseldir; gerçek bir taahhüt olarak okunmamalıdır.

### FAZ 0 — Riskli Varsayımların Doğrulanması (4–6 hafta)

> Amaç: Projeyi batırabilecek 3 belirsizliği prototiple çöz. Bu faz başarısızsa mimari revize edilir — kod atılabilir olmalı, altyapı mükemmel olmak zorunda değil.

**G-0: Keşif ve paydaşlar** *(1. hafta — diğer işlerle paralel yürür)*
- [ ] Confluence envanteri: space sayısı, toplam sayfa/ek dosya hacmi (API'den script ile) → §8 ölçek varsayımını gerçek veriyle güncelle
- [ ] Pilot aday space'leri belirle: aktif kullanılan + izin yapısı zengin 1–2 space; sahipleriyle görüş
- [ ] Kurumsal IdP'yi öğren (Azure AD / ADFS / Keycloak / diğer)
- [ ] Compliance/güvenlik sorumlusunu bul; PII politikasını (varsayılan: maskele) ve ADR-9 SLA'sını (15 dk) onaylat
- [ ] Ekip/rol netleştirme: proje sponsoru ile kapasite teyidi

**G-1: ACL-filtered retrieval PoC** *(en kritik iş — sentetik veriyle çalışır durumda, 2026-07-06)*
- [ ] 1–2 gerçek Confluence space seç, gerçek izin yapısını çıkar *(erişim bekleniyor → G-0)*
- [x] OpenFGA modeli yaz (space → page → user/group + kısıtlı sayfa semantiği) — `infra/openfga/model.fga`
- [ ] Confluence izinlerini OpenFGA'ya aktaran sync script'i *(gerçek erişim gerekli; sentetik karşılığı: `scripts/seed_synthetic.py`)*
- [x] Erişim seti materializasyonu: `ListObjects` → kullanıcı başına TTL cache'li set — `src/ragplatform/acl/access.py`
- [x] pgvector sorgusunda pre-filter ile ANN arama (hybrid + RRF); p95 latency ölçümü — `src/ragplatform/retrieval/hybrid.py`
- [x] **Kabul (sentetik):** 6 kullanıcı × 10 sorgu, 480 sonuç → sızıntı = 0, p95 = 56ms — `scripts/acl_leak_test.py`
- [ ] **Kabul (gerçek):** aynı test gerçek space + gerçek izinlerle, geniş yetkili kullanıcı (50+ space) dahil tekrarlanacak

**G-2: Embedding + reranker doğrulaması (ADR-3)** *(tam ölçüm ✅ 2026-07-19; GPU/RTX 4050)*
- [x] **Ön sinyal (sentetik set, CPU):** bge-m3 vs fake → parafraz hit@5 0.80→**1.00**, MRR 0.852→**0.931**, hit@5 **1.00**; "zafiyet↔güvenlik açığı" tipi ortak-köksüz eşleşmeler çözüldü. ACL temiz (0/480). Sonuç: `eval/results/20260706-171723_BAAI-bge-m3.json`
- [x] **Ayırt edici substrat:** 15→40 sayfa confusable korpus (`synthetic_corpus.py`) + golden_v2 (45 soru). Doygunluk kırıldı: bge-m3 hit@5 1.00→0.973 → sıralama artık ölçülebilir. *(Gerçek pilot domain korpusu — ~%90 TR, 500-1000 chunk — G-0 sonrası; sentetik karşılık bu.)*
- [x] Qwen3-Embedding-0.6B vs bge-m3 (rerank'siz, MRR/hit@k): **bge-m3 üstün** — MRR 0.937 vs 0.896, hit@1 0.919 vs 0.838, parafraz@5 eşit 0.909. `scripts/run_g2_matrix.py`
- [x] bge-reranker-v2-m3 katkısı (rerank'li vs rerank'siz): **pozitif** — bge-m3'te MRR +0.032, hit@1 +0.027, parafraz 0.909→**1.00**; latency p95 115→149ms (hedef <300 içinde). Her iki modeli de tavana (MRR 0.969) taşıyor → Faz 1'de açık.
- [x] Türkçe token verimliliği: bge-m3 **1.76** vs Qwen3 **2.62** tok/kelime (XLM-R 250k vs Qwen 151k vocab). Qwen ~%49 fazla token → daha küçük etkin bağlam + daha yüksek maliyet. `scripts/token_efficiency.py`
- [x] PG FTS `turkish` config + `unaccent` doğrulaması: çalışıyor; iki bulgu → (1) uzun sorularda AND semantiği kırılgan → OR'a geçildi, (2) t/d ünsüz yumuşamasını stemmer eşleyemiyor → chunk'a başlık gömme (contextual header) ile kapatıldı
- [x] **Kabul:** Model seçildi (bge-m3), ADR-3 kapandı; rerank katkısı ve model karşılaştırması raporlandı → `eval/results/g2-report.md`. *(Gerçek pilot içerikle tekrar doğrulama G-0 sonrası; matris tek komutla yeniden koşar.)*

**G-3: Golden eval seti v1** *(harness çalışıyor; sentetik başlangıç seti ölçüldü, 2026-07-06)*
- [ ] Domain uzmanlarıyla 50–100 soru + beklenen kaynak doküman *(pilot space sonrası; başlangıç: 22 sentetik soru — `eval/golden/golden_v1.jsonl`)*
- [x] Metrikler: hit@k (recall), MRR, yetki-sınırı ihlali, latency — `scripts/run_eval.py` *(faithfulness, generation eklendiğinde — Faz 1)*
- [x] Basit eval harness (CI entegrasyonu Faz 2'de)
- [x] **Kabul (sentetik):** set + baseline repo'da — fake embedding baseline: MRR 0.852, hit@3 0.944, parafraz hit@5 0.80. *Gerçek embedding (G-2) hedefi: parafraz ≥ 0.9.* Not: FTS, AND→OR semantiğine geçirildi (uzun Türkçe sorularda AND tek eksik kelimede ıskalıyordu; MRR 0.44→0.85)

**G-4: Altyapı iskeleti**
- [ ] K8s namespace'leri + GPU node pool (generation / embedding+rerank ayrı)
- [ ] PostgreSQL + pgvector kurulumu (HNSW parametreleri dokümante)
- [ ] OIDC entegrasyonu: Keycloak'u broker olarak kur (G-0'da IdP netleşince arkasına bağlanır — bekletmez)
- [ ] vLLM ile Qwen3 servis + smoke test
- [ ] Object storage (ham doküman kopyaları için)

**Faz 0 Çıkış Kriterleri:**
- [ ] G-0 tamamlandı: §8 varsayımları gerçek veriyle güncellendi, pilot space'ler ve IdP netleşti
- [ ] G-1 kabul kriteri sağlandı (sağlanmadıysa: mimari revizyon toplantısı)
- [x] Embedding modeli seçildi (ADR-3 ✅ bge-m3) — 2026-07-19
- [x] Golden set v1 hazır, baseline ölçüldü *(v2 40-sayfa confusable + 45 soru ile ayırt edici hale getirildi)*

---

### FAZ 1 — MVP: Uçtan Uca Çalışan Hat (6–8 hafta)

> Amaç: Tek KB (seçili Confluence space'leri), LibreChat üzerinden, ACL'li ve citation'lı soru-cevap. Sınırlı pilot kullanıcı grubu (10–20 kişi).

**Ingestion hattı**
- [ ] Confluence connector (API üzerinden sayfa + izin + metadata çekme)
- [ ] Docling ile parse (PDF/DOCX/HTML dahil); tablo ve başlık yapısı korunur
- [ ] Chunking: yapı-farkındalıklı, 300–800 token, başlık yolu (`h1 > h2 > h3`) metadata'da, tablolar bütün tutulur
- [ ] Embed + index (embedding_model_version kolonu ile — ADR-3 modeli)
- [ ] Incremental sync: değişen/silinen sayfa tespiti, idempotent re-process
- [ ] Argo Workflows DAG'ı: connector → parse → chunk → embed → index, adım bazlı retry + dead-letter
- [ ] Ham doküman kopyası object storage'a (reprocess için)

**Retrieval service**
- [ ] Hybrid arama: pgvector HNSW + PG FTS (`turkish` config + `unaccent`), RRF füzyonu (top-50)
- [ ] ACL pre-filter (G-1 deseni üretimleştirilir)
- [ ] Reranker servisi (top-50 → top-8)
- [ ] Citation: chunk → kaynak URL + başlık yolu + güncelleme tarihi
- [ ] Query rewrite (takip sorusu → bağımsız sorgu) — basit versiyonu
- [ ] API: `POST /retrieve` (user context zorunlu, ACL'siz çağrı imkânsız)

**Gateway + UI + izleme**
- [ ] LiteLLM kurulumu; ADR-5 metadata standardı middleware ile zorunlu
- [ ] LibreChat → Platform API → retrieval + generation hattı
- [ ] Langfuse: her sorgu uçtan uca trace'li (retrieval sonuçları dahil)
- [ ] Prometheus/Grafana: latency, GPU, hata oranı dashboard'ları
- [ ] Kullanıcı feedback'i (👍/👎 + yorum) → Langfuse

**Faz 1 Çıkış Kriterleri:**
- [ ] Pilot grup aktif kullanıyor; ACL sızıntısı = 0 (test edildi)
- [ ] Golden set skoru baseline'ın üzerinde; skorlar Langfuse'ta
- [ ] Uçtan uca p95 < 10 sn (retrieval p95 < 1 sn)
- [ ] Incremental sync günlük çalışıyor, hata kuyruğu boş

---

### FAZ 2 — Kurumsallaştırma: Governance + Güvenlik (8–10 hafta)

> Amaç: Pilottan kurum geneline. Control plane, güvenlik katmanı, eval kapısı, izin tazeliği. Denetimden geçebilecek durum.

**Control Plane**
- [ ] Agent Registry: agent tanımı = model + prompt ver. + KB binding + tool listesi + policy
- [ ] KB Registry: kaynak, sync durumu, sahip, veri sınıflandırması (gizlilik seviyesi)
- [ ] Prompt/Flow versiyonlama: Langfuse prompt management ile entegre; promote akışı
- [ ] Agent ↔ KB ↔ tool ↔ policy binding'leri tek yerden (orijinal madde 4)
- [ ] MCP Tool Registry: her tool için risk seviyesi (read-only / write / destructive) + onay kuralı (orijinal madde 8)
- [ ] Yüksek riskli tool çağrısında insan onayı akışı (approval UI)

**Güvenlik katmanı**
- [ ] Presidio ile ingestion'da PII tespiti; politika: maskele / etiketle / engelle (compliance ile karar)
- [ ] Retrieval içeriği "untrusted" sarmalama (ADR-8): sistem talimatı / veri ayrımı, retrieval içeriğinden tool tetiklenemez
- [ ] Output guardrail: PII maskesi, yasaklı içerik, citation zorunluluğu kontrolü
- [ ] Değiştirilemez audit log: kim, ne sordu, ne retrieve edildi, hangi tool koştu, hangi model cevapladı
- [ ] Kırmızı takım testi: zehirlenmiş doküman ile injection senaryoları (en az 10 senaryo)

**İzin tazeliği (ADR-9)**
- [ ] Confluence izin değişikliklerini yakalayan sync (webhook/poll ≤15 dk)
- [ ] Gecelik full reconciliation: kaynak sistem vs OpenFGA diff raporu
- [ ] Silinen doküman → index'ten kaldırma SLA'sı ve alarmı

**Eval kapısı + Platform API**
- [ ] Golden set 200+ soruya genişletildi; kategori bazlı (faktüel, tablo, çok-adımlı, yetki-sınırı)
- [ ] CI pipeline: prompt/flow değişikliği → offline eval → skor düşüşünde merge engeli (ADR-7)
- [ ] Platform API v1: OpenAPI spec'li, LibreChat dışı ilk tüketici entegrasyonu (Teams botu önerilir)
- [ ] Rate limit + takım bazlı bütçe/chargeback raporu (LiteLLM verisinden)

**Faz 2 Çıkış Kriterleri:**
- [ ] Güvenlik ekibi onayı (kırmızı takım bulguları kapatıldı)
- [ ] İzin iptali ≤15 dk'da yansıyor (ölçüldü)
- [ ] Eval kapısı CI'da zorunlu; en az 1 kez gerçek regresyonu yakaladı
- [ ] En az 2 tüketici (LibreChat + 1 diğer) Platform API kullanıyor

---

### FAZ 3 — Ölçek ve Optimizasyon (sürekli)

**Performans/maliyet**
- [ ] Redis exact-match cache; hit oranı raporu → semantic cache kararı
- [ ] GPU autoscaling; embedding/rerank/generation havuzlarının ayrı ölçeklenmesi
- [ ] pgvector metrikleri izleme: ADR-2 eşiklerine dashboard + alarm
- [ ] Model routing: basit sorgular küçük modele (LiteLLM routing kuralı)

**Yetenek genişletme**
- [ ] LangGraph ile ilk karmaşık flow (çok adımlı, insan onaylı) — orijinal madde 5
- [ ] Yeni kaynak connector'ları (SharePoint, dosya paylaşımları, wiki'ler)
- [ ] Multi-query / decomposition ile retrieval iyileştirme (eval ile kanıtlanarak)
- [ ] Feedback döngüsü: 👎'ler haftalık triage → golden set'e yeni vaka + iyileştirme

**Dayanıklılık**
- [ ] HA: kritik servislerin çoklu replica + PodDisruptionBudget
- [ ] Backup/restore: Postgres (pgvector dahil) + object storage; **restore tatbikatı yapıldı**
- [ ] DR planı dokümante; RTO/RPO hedefleri compliance ile anlaşıldı
- [ ] Embedding migrasyon runbook'u: dual-write → shadow eval → cutover (bir kez tatbik edildi)

---

### (arşiv) Orijinal 8 Maddenin Plana Eşlemesi

| # | Orijinal madde | Nerede |
|---|---|---|
| 1 | LibreChat'i UI olarak koru, logic dışarıda | Mimari ilke + Faz 1 (Platform API üzerinden bağlanır) |
| 2 | Gateway'e agent_id/user_id/trace_id standardı | ADR-5 + Faz 1 |
| 3 | Langfuse'u prompt ver. + trace + eval + feedback merkezi yap | Faz 1 (trace, feedback) + Faz 2 (prompt mgmt, eval) |
| 4 | Registry ile agent↔KB↔tool↔policy binding | Faz 2 Control Plane |
| 5 | LangGraph'i sadece karmaşık flow'lara sakla | Mimari ilke + Faz 3 |
| 6 | KB registry + ACL-filtered retrieval + citation | Faz 0 G-1 + Faz 1 + Faz 2 |
| 7 | Docling + incremental sync ile doküman lifecycle | Faz 1 ingestion |
| 8 | MCP tool registry: risk seviyesi + onay kuralı | Faz 2 Control Plane + ADR-8 |

---

### (arşiv) Riskler

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| ACL pre-filter ölçekte yavaş kalır | Orta | Kritik | Faz 0 G-1 PoC en başta; başarısızsa erişim seti tasarımı revize (partition bazlı index) |
| İzin drift'i → veri sızıntısı | Orta | Kritik | ≤15 dk sync + gecelik reconciliation + sızıntı testleri her release'de |
| Zehirlenmiş doküman + tool = aksiyon saldırısı | Orta | Yüksek | ADR-8 (untrusted içerik) + onay matrisi + kırmızı takım |
| Embedding modeli Türkçe'de zayıf kalır | ~~Orta~~ Düşük | Yüksek | ✅ G-2 kapattı: bge-m3 seçildi (Qwen3-0.6B'yi kalite+token veriminde geçti); reranker açık. Gerçek pilot içerikte tekrar ölçülecek (G-0). |
| pgvector ölçek tavanı | Düşük (ilk yıl) | Orta | ADR-2 eşikleri **ölçüldü** (`eval/results/scale-report.md`): sınır toplam korpus değil, kullanıcı başına görünür chunk (~25k'da p95>150ms). Geniş yetkili kullanıcılar belirleyici. Denormalizasyon denendi, işe yaramadı (daha yavaş) — kalan seçenekler: space bazlı partitioning, erişim setini daraltma, ya da native filtreli-ANN'i olan bir store (Qdrant). |
| HNSW index kurulumu veritabanını düşürür | Orta | Yüksek | Ölçüldü: 200k satırda `maintenance_work_mem=64MB` (docker varsayılanı) backend'i çökertti; paralel kurulum 64MB `/dev/shm` sınırında düşüyor. `shm_size: 1gb` eklendi; G-4'te index kurulum parametreleri dokümante edilecek. |
| Golden set bakımsız kalır, eval kapısı anlamsızlaşır | Yüksek | Orta | Feedback triage'ı ile sürekli besleme (Faz 3); set sahibi atanır |
| GPU maliyeti plansız büyür | Orta | Orta | Ayrı havuzlar + LiteLLM bütçe limitleri + chargeback görünürlüğü |
| RAGFlow yerine custom → eng eforu küçümsenir | Orta | Orta | Faz 1 kapsamı bilinçli dar: tek KB, tek akış; genişleme Faz 3'te |

---

### (arşiv) Başarı Metrikleri (KPI)

| Metrik | Hedef | Ölçüm yeri |
|---|---|---|
| ACL sızıntısı | 0 (her release'de test) | Otomatik yetki-sınırı testleri |
| Retrieval recall@10 (golden set) | ≥ 0.85 | Eval harness |
| Citation doğruluğu | ≥ 0.90 | Eval harness |
| Faithfulness (halüsinasyon yokluğu) | ≥ 0.90 | LLM-judge + örneklem insan kontrolü |
| Uçtan uca p95 latency | < 10 sn | Prometheus |
| İzin iptali yansıma süresi | ≤ 15 dk | Sync metriği |
| Kullanıcı 👍 oranı | ≥ %70 (pilot sonrası) | Langfuse |
| Aylık aktif kullanıcı | Faz 2 sonu: pilot ×5 | Platform API |

---

### (arşiv) Açık Sorular ve Çalışma Varsayımları

**Cevaplananlar:**
- [x] **Dil dağılımı:** Büyük oranda Türkçe *(2026-07-06)*. Sonuçları: G-2 test seti ~%90 Türkçe; PG FTS `turkish` config + `unaccent`; embedding/reranker seçiminde Türkçe skoru belirleyici; token verimliliği ölçümü G-2'ye eklendi.

**Cevabı henüz bilinmiyor — aşağıdaki çalışma varsayımlarıyla ilerlenir, G-0 keşif görevleriyle netleştirilir.** Varsayım yanlış çıkarsa ilgili satırdaki "etki" alanına bakıp planı güncelle:

| Soru | Çalışma varsayımı | Nasıl netleşecek | Yanlış çıkarsa etkisi |
|---|---|---|---|
| Ölçek (doküman/kullanıcı) | İlk yıl < 5M chunk, < 2K kullanıcı → pgvector güvenli bölgede | G-0: Confluence API'den envanter | Daha büyükse ADR-2 eşikleri Faz 1'de izlenmeye başlar; Qdrant değerlendirmesi öne çekilir |
| Regülasyon rejimi | KVKK taban; PII politikası = **maskele** (güvenli varsayılan) | G-0: compliance sorumlusuyla görüşme | Sektörel rejim varsa (BDDK vb.) Faz 2 güvenlik kapsamı genişler, audit gereksinimleri artar |
| İzin tazeliği SLA (ADR-9) | 15 dk | Compliance görüşmesinde onaylat | Daha sıkıysa webhook zorunlu olur (poll yetmez) |
| IdP | Keycloak **broker** olarak kurulur; kurumsal IdP arkasına bağlanır | G-0: IT'den öğren | Düşük — broker deseni her IdP'yi sonradan kabul eder |
| Pilot grubu | İzin yapısı zengin + aktif 1–2 space (G-0'da seçilecek) | G-0: envanter + sahiplerle görüşme | Pilot seçimi gecikirse G-1 sentetik izin yapısıyla başlar (gerçek space ile tekrar doğrulanır) |
| Ekip | 3–4 mühendis | Sponsor ile teyit | Daha azsa faz süreleri uzar; kapsam daraltma önceliği: Faz 2 Platform API → Faz 3'e itilir |
