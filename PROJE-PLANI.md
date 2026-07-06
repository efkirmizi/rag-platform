# Kurumsal RAG Platformu — Proje Planı

> **Son güncelleme:** 2026-07-06
> **Durum:** Faz 0 devam ediyor — G-1 sentetik PoC ✅ (sızıntı 0/480, p95 ~60ms) · G-3 harness + sentetik baseline ✅ (MRR 0.852). Sırada: G-0 keşif (kurum bilgileri) ve G-2 (gerçek embedding — vLLM/GPU erişimi gerekli). Kod: `src/ragplatform/`, kurulum: `README.md`
> **Takip kuralı:** Görevler `- [ ]` / `- [x]` ile işaretlenir. Her faz sonunda "Faz Çıkış Kriterleri" sağlanmadan sonraki faza geçilmez. Kararlar §3'e (ADR), yeni riskler §6'ya eklenir.

---

## 1. Vizyon ve Kapsam

Kurum içi dokümanlar (Confluence, PDF/DOCX/HTML) üzerinde, **erişim yetkilerine tam saygılı**, kaynak gösteren (citation), izlenebilir ve yönetilebilir bir AI platformu. LibreChat ilk tüketici; platform API'si üzerinden Teams/Slack/iç uygulamalar da bağlanabilir.

**Kapsam dışı (v1):** Fine-tuning, ses/görüntü, internet araması, otonom yazma aksiyonları (tool'lar onay matrisine tabi).

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
| ADR-2 | pgvector ile başla; **çıkış eşiği:** >20M chunk VEYA p95 filtreli ANN >150ms VEYA index build >4saat → Qdrant migrasyonu değerlendir | ✅ Karar | Migrasyon hedefi Qdrant (metadata filtre + ölçek dengesi). |
| ADR-3 | Embedding modeli seçimi | ⬜ Faz 0'da | Qwen3-Embedding vs bge-m3, Türkçe+domain golden set ile ölçülecek. |
| ADR-4 | ACL deseni: OpenFGA `ListObjects` → erişim seti → pgvector sorgusunda metadata pre-filter | ✅ Karar | Faz 0 PoC ile doğrulanacak; başarısızsa mimari revize edilir. |
| ADR-5 | Gateway metadata standardı: `agent_id, user_id, trace_id, kb_ids[], prompt_version, flow_version` her LLM çağrısında zorunlu | ✅ Karar | LiteLLM middleware'de enforce edilir; eksikse çağrı reddedilir. |
| ADR-6 | Ingestion: Argo Workflows + Postgres outbox; Kafka yalnız >100K doküman/gün olursa | ✅ Karar | Erken Kafka = gereksiz operasyonel yük. |
| ADR-7 | Eval kapısı: golden set regresyonu geçmeyen prompt/flow versiyonu prod'a çıkamaz | ✅ Karar | CI pipeline'da zorunlu adım. |
| ADR-8 | Retrieval içeriği "untrusted" işaretlenir; tool çağrısı tetikleyemez | ✅ Karar | Indirect prompt injection savunmasının temeli. |
| ADR-9 | İzin tazeliği hedefi: kaynak sistemde iptal edilen erişim ≤15 dk içinde retrieval'a yansır | ⬜ Onay bekliyor | Compliance ekibiyle SLA netleştirilecek. |

---

## 4. Yol Haritası

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

**G-2: Embedding + reranker doğrulaması (ADR-3)**
- [ ] Domain korpusundan 500–1000 chunk'lık test seti hazırla (**~%90 Türkçe** — gerçek içerik dağılımını yansıt)
- [ ] Qwen3-Embedding vs bge-m3: recall@10 / MRR karşılaştır (Türkçe skoru belirleyici)
- [ ] bge-reranker-v2-m3'ün Türkçe'de katkısını ölç (rerank'li vs rerank'siz)
- [ ] Türkçe token verimliliğini ölç (token/kelime oranı → bağlam bütçesi ve maliyet planı buna göre)
- [ ] PG FTS `turkish` config + `unaccent` ile lexical arama kalitesini hızlıca doğrula (eklemeli yapıda stemming yeterli mi?)
- [ ] **Kabul:** Model seçildi, ADR-3 kapandı; rerank katkısı ve FTS doğrulaması raporlandı

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
- [ ] Embedding modeli seçildi (ADR-3 ✅)
- [ ] Golden set v1 hazır, baseline ölçüldü

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

## 5. Orijinal 8 Maddenin Plana Eşlemesi

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

## 6. Riskler

| Risk | Olasılık | Etki | Azaltma |
|---|---|---|---|
| ACL pre-filter ölçekte yavaş kalır | Orta | Kritik | Faz 0 G-1 PoC en başta; başarısızsa erişim seti tasarımı revize (partition bazlı index) |
| İzin drift'i → veri sızıntısı | Orta | Kritik | ≤15 dk sync + gecelik reconciliation + sızıntı testleri her release'de |
| Zehirlenmiş doküman + tool = aksiyon saldırısı | Orta | Yüksek | ADR-8 (untrusted içerik) + onay matrisi + kırmızı takım |
| Embedding modeli Türkçe'de zayıf kalır | Orta | Yüksek | Faz 0 G-2 ölçümü; bge-m3 yedek aday |
| pgvector ölçek tavanı | Düşük (ilk yıl) | Orta | ADR-2 eşikleri + izleme; Qdrant çıkış planı hazır |
| Golden set bakımsız kalır, eval kapısı anlamsızlaşır | Yüksek | Orta | Feedback triage'ı ile sürekli besleme (Faz 3); set sahibi atanır |
| GPU maliyeti plansız büyür | Orta | Orta | Ayrı havuzlar + LiteLLM bütçe limitleri + chargeback görünürlüğü |
| RAGFlow yerine custom → eng eforu küçümsenir | Orta | Orta | Faz 1 kapsamı bilinçli dar: tek KB, tek akış; genişleme Faz 3'te |

---

## 7. Başarı Metrikleri (KPI)

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

## 8. Açık Sorular ve Çalışma Varsayımları

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
