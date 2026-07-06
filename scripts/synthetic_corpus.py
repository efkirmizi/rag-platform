# -*- coding: utf-8 -*-
"""G-1 PoC için sentetik kurum içeriği ve izin yapısı (PROJE-PLANI.md §8: pilot
space erişimi gelene kadar sentetik izin yapısıyla ilerle).

Senaryo — 3 space, 6 kullanıcı, 7 grup:
- IK  : herkese açık (grp herkes), 2 kısıtlı sayfa (yalnız ik-yonetim)
- ENG : yalnız grp eng, 1 kısıtlı sayfa (yalnız guvenlik)
- FIN : yalnız grp fin, 1 kısıtlı sayfa (yalnız fin-yonetim)

Gerçek Confluence connector'ı geldiğinde bu modülün yerini connector alır;
seed ve test script'leri buradaki yapıdan bağımsız hesap yapar.
"""

SPACES = {
    "IK": "İnsan Kaynakları",
    "ENG": "Mühendislik",
    "FIN": "Finans",
}

USERS = ["ayse", "mehmet", "can", "zeynep", "deniz", "elif"]

GROUPS = {
    "herkes": ["ayse", "mehmet", "can", "zeynep", "deniz", "elif"],
    "ik": ["ayse", "zeynep"],
    "ik-yonetim": ["zeynep"],
    "eng": ["mehmet", "deniz"],
    "guvenlik": ["deniz"],
    "fin": ["can", "elif"],
    "fin-yonetim": ["elif"],
}

# space -> viewer grupları
SPACE_VIEWERS = {
    "IK": ["herkes"],
    "ENG": ["eng"],
    "FIN": ["fin"],
}

PAGES = [
    {
        "page_key": "ik-yillik-izin",
        "space": "IK",
        "title": "Yıllık izin politikası",
        "restricted_to": None,
        "content": """## Hak edilen izin süreleri
Kıdemi 1-5 yıl arasında olan çalışanlar yılda 14 iş günü, 5-15 yıl arasında
olanlar 20 iş günü, 15 yıldan fazla olanlar 26 iş günü yıllık ücretli izin
hakkına sahiptir. İzin hakları takvim yılı bazında hesaplanır ve bir sonraki
yıla en fazla 5 gün devredilebilir.

## Onay akışı
İzin talepleri İK portalı üzerinden en az 5 iş günü önceden girilir. Talep,
önce birim yöneticisi onayına düşer; 10 iş gününü aşan talepler ayrıca
departman direktörü onayı gerektirir. Onaylanan izinler ekip takvimine
otomatik işlenir.

## Hastalık izni
Hastalık durumunda ilk iş günü içinde yöneticinize bilgi vermeniz gerekir.
İki günü aşan raporlu izinlerde sağlık raporunun İK portalına yüklenmesi
zorunludur.""",
    },
    {
        "page_key": "ik-uzaktan-calisma",
        "space": "IK",
        "title": "Uzaktan çalışma esasları",
        "restricted_to": None,
        "content": """## Hibrit çalışma modeli
Çalışanlar haftada en fazla 3 gün uzaktan çalışabilir. Salı ve perşembe
günleri ofis günüdür; tüm ekipler bu günlerde ofiste bulunur. Çekirdek
çalışma saatleri 10:00-16:00 arasıdır.

## Ekipman ve güvenlik
Uzaktan çalışmada şirket cihazı kullanımı zorunludur. Kişisel cihazlardan
kurumsal sistemlere erişim yasaktır. VPN bağlantısı olmadan iç ağ
kaynaklarına erişilemez; kurulum için Mühendislik alanındaki VPN kılavuzuna
bakınız.""",
    },
    {
        "page_key": "ik-ise-alim",
        "space": "IK",
        "title": "İşe alım süreci",
        "restricted_to": None,
        "content": """## Süreç adımları
İşe alım süreci dört aşamadan oluşur: özgeçmiş taraması, İK ön görüşmesi,
teknik/yetkinlik mülakatı ve yönetici mülakatı. Her aşamanın sonucu 3 iş
günü içinde adaya bildirilir.

## Teklif ve başlangıç
Teklif mektubu, referans kontrolü tamamlandıktan sonra gönderilir. İşe
başlangıç evrakları ilk gün İK'ya teslim edilir; oryantasyon programı ilk
hafta boyunca sürer.""",
    },
    {
        "page_key": "ik-performans",
        "space": "IK",
        "title": "Performans değerlendirme dönemi",
        "restricted_to": None,
        "content": """## Değerlendirme takvimi
Performans değerlendirmeleri yılda iki kez, haziran ve aralık aylarında
yapılır. Öz değerlendirme formu dönem başında açılır ve iki hafta açık
kalır.

## Hedef belirleme
Hedefler çeyrek bazında belirlenir ve yönetici ile birebir görüşmede
netleştirilir. Hedeflerin ölçülebilir olması ve en geç dönemin ilk ayında
sisteme girilmesi gerekir.""",
    },
    {
        "page_key": "ik-maas-bantlari",
        "space": "IK",
        "title": "Maaş bantları ve seviye matrisi",
        "restricted_to": "ik-yonetim",
        "content": """## Seviye yapısı
Mühendislik kadroları L1-L7 arasında yedi seviyede tanımlıdır. Her seviyenin
maaş bandı alt, orta ve üst çeyrek olarak üç dilimde yönetilir. Bant dışı
teklifler ücret komitesi onayı gerektirir.

## Yıllık ayarlama
Maaş bantları her yıl ocak ayında piyasa verisiyle güncellenir. Enflasyon
ayarlaması ve performans artışı ayrı kalemler olarak uygulanır. Bant
bilgileri gizlidir ve yalnız İK yönetimi ile paylaşılır.""",
    },
    {
        "page_key": "ik-isten-cikis",
        "space": "IK",
        "title": "İşten çıkış prosedürü",
        "restricted_to": "ik-yonetim",
        "content": """## Çıkış süreci
İstifa bildirimleri yazılı olarak alınır ve ihbar süresi sözleşmeye göre
hesaplanır. Çıkış mülakatı son hafta içinde İK tarafından yapılır; erişim
iptalleri son iş günü mesai bitiminde tamamlanır.

## Erişim iptali kontrol listesi
Kurumsal hesaplar, VPN erişimi, ofis kartı ve tüm SaaS lisansları çıkış
gününde kapatılır. Erişim iptali 15 dakika içinde tüm sistemlere yansımak
zorundadır; gecikme güvenlik ihlali olarak raporlanır.""",
    },
    {
        "page_key": "eng-vpn",
        "space": "ENG",
        "title": "VPN kurulum kılavuzu",
        "restricted_to": None,
        "content": """## İstemci kurulumu
Kurumsal VPN istemcisi self-servis portalından indirilir. Kurulum sonrası
ilk bağlantıda cihaz sertifikası otomatik yüklenir. Bağlantı adresi
vpn.sirket.local, kimlik doğrulama SSO üzerinden yapılır.

## Sık karşılaşılan hatalar
TR-4021 hata kodu sertifika süresinin dolduğunu gösterir; portaldan
sertifika yenileme adımını çalıştırın. TR-4030 hatası MFA zaman aşımıdır;
telefonunuzun saat ayarını kontrol edin. Bağlantı kopmalarında önce
istemciyi yeniden başlatın, sorun sürerse #bt-destek kanalına yazın.""",
    },
    {
        "page_key": "eng-kod-inceleme",
        "space": "ENG",
        "title": "Kod inceleme standartları",
        "restricted_to": None,
        "content": """## İnceleme kuralları
Her değişiklik en az bir onay almadan ana dala birleştirilemez. 400 satırı
aşan değişiklikler parçalara bölünmelidir. İncelemeci 24 saat içinde ilk
geri bildirimi vermekle yükümlüdür.

## Otomatik kontroller
CI hattında lint, birim testleri ve güvenlik taraması zorunludur. Kırmızı
CI ile birleştirme teknik olarak engellidir; acil durum istisnası yalnız
nöbetçi mühendis onayıyla kullanılabilir.""",
    },
    {
        "page_key": "eng-dagitim",
        "space": "ENG",
        "title": "Üretim ortamına dağıtım süreci",
        "restricted_to": None,
        "content": """## Dağıtım pencereleri
Üretim dağıtımları hafta içi 10:00-16:00 arasında yapılır. Cuma öğleden
sonra ve resmi tatil öncesi dağıtım yapılmaz. Her dağıtım kademeli açılır:
önce %5 trafik, 30 dakika gözlem, sonra tam açılım.

## Geri alma
Her dağıtımın tek komutla geri alınabilir olması zorunludur. Geri alma
kararı, hata oranı eşiği aşıldığında nöbetçi mühendis tarafından beklemeden
verilir; yönetici onayı gerekmez.""",
    },
    {
        "page_key": "eng-olay-mudahale",
        "space": "ENG",
        "title": "Olay müdahale runbook",
        "restricted_to": None,
        "content": """## Önem seviyeleri
SEV1 tam kesinti, SEV2 kritik işlev kaybı, SEV3 kısmi bozulma demektir.
SEV1 olaylarında 15 dakika içinde olay kanalı açılır ve olay yöneticisi
atanır.

## Müdahale adımları
İlk adım etkiyi durdurmaktır; kök neden analizi olay kapandıktan sonra
yapılır. Tüm müdahale adımları olay kanalına zaman damgasıyla yazılır.
Olay sonrası inceleme (postmortem) 5 iş günü içinde yayımlanır ve suçlama
içermez.""",
    },
    {
        "page_key": "eng-guvenlik-acigi",
        "space": "ENG",
        "title": "Güvenlik açığı bildirim süreci",
        "restricted_to": "guvenlik",
        "content": """## Bildirim kanalı
Güvenlik açığı şüphesi yalnız guvenlik@sirket.local adresine veya gizli
#guvenlik-bildirim kanalına raporlanır. Açık detayları genel kanallarda
paylaşılamaz; embargo süreci güvenlik ekibi tarafından yönetilir.

## Değerlendirme ve yamalama
Bildirimler 24 saat içinde triyaj edilir. Kritik açıklarda yama süresi 72
saattir; istismar edilebilirlik doğrulanırsa etkilenen sistemler önce
ağdan izole edilir. Ödül programı kapsamındaki bildirimler ayrıca
değerlendirilir.""",
    },
    {
        "page_key": "fin-masraf",
        "space": "FIN",
        "title": "Masraf beyan süreci",
        "restricted_to": None,
        "content": """## Beyan kuralları
Masraflar, harcamayı izleyen 30 gün içinde masraf sisteminden beyan edilir.
Fiş veya fatura görseli olmayan kalemler reddedilir. Yemek, ulaşım ve
konaklama kalemleri için günlük üst limitler finans portalında yayımlanır.

## Onay ve ödeme
1.000 TL altı masraflar yönetici onayıyla, üzeri masraflar finans kontrol
onayıyla ödenir. Onaylanan masraflar takip eden ilk maaş ödemesiyle
birlikte yatırılır.""",
    },
    {
        "page_key": "fin-satinalma",
        "space": "FIN",
        "title": "Satın alma onay limitleri",
        "restricted_to": None,
        "content": """## Onay matrisi
50.000 TL'ye kadar satın almalar birim yöneticisi, 250.000 TL'ye kadar
direktör, üzeri tutarlar genel müdür onayı gerektirir. Yazılım lisansları
tutardan bağımsız olarak BT mimari onayından geçer.

## Tedarikçi kaydı
Yeni tedarikçiyle çalışmadan önce tedarikçi kayıt formu ve vergi levhası
finansa iletilir. Kayıt tamamlanmadan sipariş açılamaz.""",
    },
    {
        "page_key": "fin-butce",
        "space": "FIN",
        "title": "Bütçe planlama takvimi",
        "restricted_to": None,
        "content": """## Yıllık döngü
Bütçe çalışması eylül ayında başlar; birim bütçeleri ekim sonuna kadar
finansa iletilir. Konsolidasyon kasımda tamamlanır ve yönetim kurulu onayı
aralık ilk haftasında alınır.

## Revizyon
Çeyrek kapanışlarında bütçe gerçekleşme raporu yayımlanır. Yüzde 10'u aşan
sapmalar için revizyon talebi gerekçesiyle birlikte finansa sunulur.""",
    },
    {
        "page_key": "fin-tedarikci-odeme",
        "space": "FIN",
        "title": "Tedarikçi ödeme koşulları",
        "restricted_to": "fin-yonetim",
        "content": """## Ödeme vadeleri
Standart tedarikçi vadesi 45 gündür; stratejik tedarikçilerle özel vade
anlaşmaları finans yönetimi onayıyla yapılır. Erken ödeme iskontosu yıllık
çerçeve sözleşmede tanımlıysa uygulanır.

## Gizli ticari koşullar
Tedarikçi bazlı iskonto oranları ve özel fiyat anlaşmaları gizlidir; yalnız
finans yönetimi erişebilir. Bu bilgiler ihale süreçlerinde pazarlık gücünü
korumak için kısıtlı tutulur.""",
    },
]


def expected_allowed_spaces(user: str) -> set[str]:
    """Kullanıcının görebilmesi GEREKEN space seti — FGA'dan bağımsız hesap.

    Leak testi bunu FGA/SQL sonuçlarıyla karşılaştırır; iki yol aynı kaynaktan
    beslenmediği için modelleme hatalarını da yakalar.
    """
    user_groups = {g for g, members in GROUPS.items() if user in members}
    return {
        space
        for space, viewer_groups in SPACE_VIEWERS.items()
        if user_groups & set(viewer_groups)
    }


def expected_allowed_pages(user: str) -> set[str]:
    """Kullanıcının görebilmesi gereken page_key seti (kısıt semantiği dahil)."""
    user_groups = {g for g, members in GROUPS.items() if user in members}
    spaces = expected_allowed_spaces(user)
    allowed = set()
    for page in PAGES:
        if page["space"] not in spaces:
            continue
        if page["restricted_to"] is None or page["restricted_to"] in user_groups:
            allowed.add(page["page_key"])
    return allowed
