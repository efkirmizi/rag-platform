# Ölçek testi — ACL-filtreli ANN (ADR-2 / ADR-4)

> Üretim: `scripts/scale_test.py` · pgvector 0.8.4 / PostgreSQL 16.14 (Docker)
> 100.000 chunk · 1024 boyut · 400 space · 400 konu kümesi · k=10 · 20 sorgu/hücre

## Neden bu test

G-1'in tüm latency sayıları **106 chunk** üzerinde ölçüldü. O boyutta planlayıcı
HNSW index'ini hiç kullanmıyor — yani projenin ölçtüğü her şey "index'siz"
rakamdı ve ADR-2'nin çıkış eşiği ("p95 filtreli ANN > 150ms") hiç koşmamış bir
kod yoluna aitti. Bu test o boşluğu kapatır.

## Bulgu 1 — Planlayıcı filtre varken index'i seçmiyor (bugünkü davranış)

| görünür satır | index kullanıldı | recall | p95 |
|---:|:--:|:--:|---:|
| 100.000 (%100) | **evet** | 1.000 | 485–552 ms |
| 25.118 (%25) | hayır | 1.000 | 180–198 ms |
| 9.985 (%10) | hayır | 1.000 | 55–72 ms |
| 2.997 (%3) | hayır | 1.000 | 22–24 ms |
| 1.063 (%1) | hayır | 1.000 | 13–18 ms |

Yetki filtresi seçiciyse Postgres HNSW'yi bırakıp **izinli alt kümeyi seq scan**
ediyor. Sonuç tam (recall 1.000) ama maliyet **kullanıcının gördüğü satır
sayısıyla doğrusal**. Yani:

- ✅ **ADR-4 doğruluk açısından güvenli**: pre-filter sonuç kaybettirmiyor.
- ⚠️ Dar yetkili kullanıcı hızlı (13ms), geniş yetkili kullanıcı yavaş.
- ⚠️ **781 MB'lık HNSW index normal yolda kullanılmıyor** (tablo 1.317 MB).
- ⚠️ ADR-2'nin 150ms eşiği ~**25.000 görünür chunk** civarında aşılıyor.

## Bulgu 2 — Index kullanıldığında varsayılan ayar sonuçları bozuyor ⚠️

`enable_seqscan=off` ile planlayıcı zorlandığında HNSW gerçekten kullanılıyor
(`Index Scan using scale_chunks_hnsw` → Nested Loop → `pages` filtresi).
30.000 satır, kullanıcı korpusun %10'unu görüyor:

| `hnsw.iterative_scan` | recall | 10 sonuçtan eksik |
|---|:--:|:--:|
| `off` — **pgvector varsayılanı** | **0.367** | **6.3** |
| `relaxed_order` | 0.967 | 0.0 |

Filtre index taramasından sonra uygulandığı için, varsayılan ayarda index ilk
`ef_search` adayını döndürüyor, yetki filtresi çoğunu eliyor ve sorgu hem k
sonucu dolduramıyor hem de doğru komşuları kaçırıyor.

**Bu risk bugün gizli**: planlayıcı henüz index'i seçmiyor. Korpus büyüyüp
maliyet dengesi index lehine döndüğünde, ayar olmadan **dar yetkili
kullanıcılara sessizce eksik ve kalitesiz sonuç** dönmeye başlar — hata vermeden.

### Uygulanan önlem

`src/ragplatform/db.py` artık her bağlantıda `hnsw.iterative_scan=relaxed_order`
ayarlıyor (pgvector <0.8'de sessizce atlanır). Planlayıcı index'i seçmeye
başladığında doğru davranış hazır olacak.

## Bulgu 3 — Index kurulumu operasyonel bir risk

- 200k satırda HNSW kurulumu, Docker varsayılanı `maintenance_work_mem=64MB`
  ile **backend'i çökertti** (`exit code 2` → veritabanı recovery'ye girdi;
  aynı örneğe bağlı diğer servisler de düştü).
- Paralel kurulum Docker'ın 64MB `/dev/shm` sınırında
  `No space left on device` ile düşüyor → `docker-compose.yml`'ye `shm_size: 1gb`
  eklendi.
- 100k satırda: kurulum 40–47 sn, index 781 MB. Doğrusal varsayarsak 5M chunk →
  ~35–40 GB index ve ~35–40 dk kurulum (ADR-2'nin "build > 4 saat" eşiğinin
  altında ama diskte ciddi yer).

## ADR-2 / ADR-4 için sonuç

1. **ADR-4 (pre-filter) doğruluk açısından doğrulandı** — sızıntı yok, sonuç kaybı yok.
2. **ADR-2 eşiği somutlaştı**: p95 > 150ms, ~25k görünür chunk civarında geliyor;
   bu bir *toplam korpus* değil *kullanıcı başına görünürlük* eşiği. Geniş
   yetkili kullanıcılar (plan §G-1: "50+ space'li kullanıcı dahil test edilecek")
   belirleyici olacak.
3. **Denenmesi gereken bir sonraki adım**: `space_key`'i `chunks` tablosuna
   denormalize edip filtre ile vektörü aynı tabloya almak; böylece planlayıcı
   JOIN'siz bir index yolu değerlendirebilir (kısmi/bileşik index seçenekleri
   açılır). Bu test edilmeden Qdrant migrasyonu düşünülmemeli.

## Yeniden üretim

```powershell
python scripts/scale_test.py --rows 100000 --spaces 400 --clusters 400 `
  --selectivity 1.0 0.25 0.1 0.03 0.01 --maintenance-mem 2GB
```

⚠️ Ağır iş: paylaşılan bir Postgres'te çalıştırmayın (yukarıdaki çökme notu).

### Ölçüm geçerliliği notu

Harness, güvenilir sayı üretmeden önce üç ölçüm hatası verdi ve düzeltildi:
1024 boyutta gürültü normunun merkezleri ezmesi (yapısız veri), sorguların
rastgele yönde üretilmesi (yüksek boyutta "en yakın komşu" anlamsızlaşır) ve
`LATERAL`'in dış satıra bağımlı olmaması yüzünden Postgres'in gürültüyü bir kez
üretip **binlerce özdeş vektörde** yeniden kullanması. Sonuncusu recall'ı
tie-breaking gürültüsüne çeviriyordu; script artık üretim sonrası yinelenen
vektör denetimi yapıp bu durumda hata veriyor.
