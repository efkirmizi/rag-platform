import asyncpg

# pgvector 0.8+ ayarı. ACL pre-filter'lı ANN'de KRİTİK:
#
# HNSW yaklaşık aramadır ve JOIN'den gelen yetki filtresi index taramasından
# SONRA uygulanır. `iterative_scan=off` (pgvector varsayılanı) ile index ilk
# ef_search adayı döndürür, filtre çoğunu eler ve sorgu hem k sonucu dolduramaz
# hem de recall çöker. Ölçüldü (scripts/scale_test.py, 30k satır, kullanıcı
# korpusun %10'unu görüyor, index kullanımı zorlanmış):
#
#     iterative_scan=off            recall 0.367 · 10 sonuçtan 6.3'ü EKSİK
#     iterative_scan=relaxed_order  recall 0.967 · eksik yok
#
# Bugün planlayıcı filtreli sorgularda çoğunlukla seq scan seçiyor (tam sonuç,
# maliyet görünür satır sayısıyla doğrusal), yani sorun GİZLİ. Korpus büyüyüp
# maliyet dengesi index lehine döndüğünde, bu ayar olmadan dar yetkili
# kullanıcılara sessizce eksik sonuç dönmeye başlar.
_HNSW_ITERATIVE_SCAN = "relaxed_order"


async def _init_connection(conn: asyncpg.Connection) -> None:
    try:
        # GUC'ler pgvector kütüphanesi oturuma yüklenene kadar tanımlı değil;
        # önce ucuz bir vector işlemiyle yüklenmesini tetikle.
        await conn.execute("SELECT '[1]'::vector <=> '[1]'::vector")
        await conn.execute(f"SET hnsw.iterative_scan = {_HNSW_ITERATIVE_SCAN}")
    except Exception:
        # Eski pgvector (<0.8) bu ayarı tanımaz — bağlantıyı düşürmeye değmez.
        pass


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=10, init=_init_connection)
