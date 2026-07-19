# -*- coding: utf-8 -*-
"""G-1 PoC + G-2 ölçümü için sentetik kurum içeriği ve izin yapısı
(PROJE-PLANI.md §8: pilot space erişimi gelene kadar sentetik izin yapısıyla ilerle).

Senaryo — 3 space, 6 kullanıcı, 7 grup, 40 sayfa:
- IK  : herkese açık (grp herkes), 3 kısıtlı sayfa (yalnız ik-yonetim)
- ENG : yalnız grp eng, 2 kısıtlı sayfa (yalnız guvenlik)
- FIN : yalnız grp fin, 2 kısıtlı sayfa (yalnız fin-yonetim)

G-2 için içerik bilinçli olarak **confusable kümeler** halinde genişletildi:
izin (yıllık/hastalık/doğum/ücretsiz/tatil), erişim (uzaktan/VPN/ağ/ekipman),
masraf (masraf/seyahat/kart/avans), güvenlik (açık/olay/parola/sınıflandırma),
dağıtım (dağıtım/sürümleme/test/nöbet). Her sorgunun 4-5 makul adayı olur →
sıralama zorlaşır → reranker ve embedding farkı ölçülebilir hale gelir
(doygun set sorunu, bkz. docs/superpowers/specs/2026-07-19-...-design.md §1.1).

İlk 15 sayfa (G-1 baseline'ı) DEĞİŞTİRİLMEDEN korunur; page_key'ler sabittir.
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
    # ---------------------------------------------------------------------
    # G-2 confusable küme genişletmesi — aşağıdaki 25 sayfa yeni.
    # ---------------------------------------------------------------------
    # --- İzin kümesi (IK, herkese açık) ---
    {
        "page_key": "ik-hastalik-izni",
        "space": "IK",
        "title": "Hastalık izni ve sağlık raporu",
        "restricted_to": None,
        "content": """## Rapor bildirimi
Hastalık nedeniyle işe gelemeyecek çalışan, mesai başlangıcından önce
yöneticisine ve İK'ya bilgi verir. Tek günlük rahatsızlıklarda sözlü bildirim
yeterlidir.

## Sağlık raporu
İki iş gününü aşan hastalık izinlerinde resmi sağlık raporu İK portalına 48
saat içinde yüklenir. Raporlu günler yıllık izinden düşülmez; SGK iş
göremezlik süreci İK tarafından başlatılır.

## Uzun süreli rapor
Yirmi günü aşan raporlarda iş yeri hekimi görüşü istenir ve işe dönüşte
kontrol muayenesi yapılır.""",
    },
    {
        "page_key": "ik-dogum-izni",
        "space": "IK",
        "title": "Doğum ve ebeveyn izni",
        "restricted_to": None,
        "content": """## Analık izni
Kadın çalışanlar doğumdan önce 8, doğumdan sonra 8 hafta olmak üzere toplam 16
hafta ücretli analık izni kullanır. Çoğul gebelikte doğum öncesine 2 hafta
eklenir.

## Babalık ve evlat edinme
Babalık izni 5 iş günüdür. Evlat edinmede eşlerden birine 8 hafta izin hakkı
doğar. İzinler İK portalından belge ile talep edilir.

## Süt izni ve dönüş
Doğum sonrası ilk bir yıl günde 1,5 saat süt izni verilir. İzin dönüşünde
talep hâlinde 6 aya kadar kısmi veya uzaktan çalışma değerlendirilir.""",
    },
    {
        "page_key": "ik-ucretsiz-izin",
        "space": "IK",
        "title": "Ücretsiz izin esasları",
        "restricted_to": None,
        "content": """## Ücretsiz izin hakkı
Yıllık ücretli izni tükenen çalışan, geçerli mazeretle yılda en fazla 30 gün
ücretsiz izin talep edebilir. Talep, yöneticisi ve İK'nın ortak onayına
tabidir.

## Etki ve şartlar
Ücretsiz izin süresince maaş ve yan haklar durur; sağlık sigortası çalışan
talebiyle sürdürülebilir. Bir aydan uzun ücretsiz izinlerde kıdem süresi
işlemez.

## Analık sonrası ek izin
Analık izni bitiminde talep edilirse 6 aya kadar ek ücretsiz izin verilir; bu
süre performans döneminde orantılı değerlendirilir.""",
    },
    {
        "page_key": "ik-resmi-tatil",
        "space": "IK",
        "title": "Resmi tatil takvimi",
        "restricted_to": None,
        "content": """## Resmi tatil günleri
Ulusal bayramlar, dini bayramlar ve yılbaşı resmi tatildir. Dini bayram
arifelerinde yarım gün çalışılır. Tatil takvimi her yıl aralık ayında İK
tarafından yayımlanır.

## Tatilde çalışma
Resmi tatilde çalışan personele karşılığı fazla mesai ya da serbest gün olarak
verilir. Nöbet gerektiren birimler tatil çalışma planını bir hafta önceden
bildirir.

## Köprü günleri
Tatil ile hafta sonu arasına denk gelen köprü günleri, yıllık izinden
düşülerek idari izin biçiminde kullandırılabilir; karar yönetimce duyurulur.""",
    },
    # --- Erişim / ekipman kümesi (IK + ENG) ---
    {
        "page_key": "ik-ekipman-zimmet",
        "space": "IK",
        "title": "Ekipman zimmet ve iade",
        "restricted_to": None,
        "content": """## Zimmet süreci
İşe başlayan çalışana dizüstü bilgisayar, ekran ve gerekli çevre birimleri
zimmetle teslim edilir. Zimmet formu imzalanmadan cihaz verilmez.

## Kullanım ve bakım
Zimmetli cihazlar yalnız iş amaçlı kullanılır; kişisel yazılım kurulumu BT
onayına tabidir. Arıza durumunda BT destek kaydı açılır ve geçici cihaz
sağlanır.

## İade
Görevden ayrılışta tüm zimmetli ekipman son iş günü İK'ya iade edilir. İade
edilmeyen cihaz bedeli son ödemeden mahsup edilir.""",
    },
    {
        "page_key": "ik-ofis-kullanim",
        "space": "IK",
        "title": "Ofis kullanım ve masa rezervasyonu",
        "restricted_to": None,
        "content": """## Masa rezervasyonu
Hibrit düzende ofise gelen çalışanlar masalarını rezervasyon uygulamasından
ayırtır. Salı ve perşembe ekip günlerinde masalar ekiplere bloke edilir.

## Ortak alanlar
Toplantı odaları takvimden rezerve edilir; 8 kişiden büyük toplantılar için
konferans salonu kullanılır. Mutfak ve dinlenme alanları paylaşımlıdır.

## Ziyaretçi ve güvenlik
Ziyaretçiler resepsiyondan kayıtla giriş yapar ve refakatle ağırlanır. Ofis
giriş kartı başkasıyla paylaşılmaz; kayıp kart derhal güvenliğe bildirilir.""",
    },
    {
        "page_key": "ik-oryantasyon",
        "space": "IK",
        "title": "Oryantasyon ve işe uyum",
        "restricted_to": None,
        "content": """## İlk hafta programı
Yeni çalışanın ilk günü İK karşılaması, evrak teslimi ve ekipman zimmetiyle
başlar. İlk hafta boyunca şirket tanıtımı, süreçler ve araçlar üzerine
oryantasyon oturumları yapılır.

## Mentorluk
Her yeni çalışana bir mentor atanır; ilk üç ay boyunca haftalık birebir
görüşme yapılır. Mentor, ekibe uyum ve süreçlerde rehberlik eder.

## Deneme süresi
Deneme süresi iki aydır; sonunda yönetici değerlendirmesi yapılır. Olumlu
değerlendirmede kadro kalıcılaşır.""",
    },
    {
        "page_key": "ik-egitim-gelisim",
        "space": "IK",
        "title": "Eğitim ve gelişim politikası",
        "restricted_to": None,
        "content": """## Eğitim bütçesi
Her çalışana yıllık kişisel gelişim bütçesi tanımlanır; kurs, konferans ve
sertifika bu bütçeden karşılanır. Talep yönetici onayıyla eğitim sistemine
girilir.

## İç eğitimler
Teknik ve yetkinlik eğitimleri iç eğitmenlerce düzenli verilir. Katılım
eğitim kataloğundan yapılır; tamamlanan eğitimler gelişim planına işlenir.

## Sertifikasyon
Şirketin desteklediği sertifikalarda sınav ücreti karşılanır; başarısız sınav
bir kez daha desteklenir. Sertifika sonrası bilgi paylaşım oturumu beklenir.""",
    },
    {
        "page_key": "ik-disiplin",
        "space": "IK",
        "title": "Disiplin ve savunma süreci",
        "restricted_to": None,
        "content": """## Disiplin süreci
Kurallara aykırı davranışlarda kademeli süreç uygulanır: sözlü uyarı, yazılı
uyarı, savunma talebi ve gerekirse iş akdinin feshi. Her aşama İK tarafından
kayıt altına alınır.

## Savunma hakkı
Yazılı uyarı öncesi çalışandan yazılı savunma istenir; savunma için en az 3 iş
günü verilir. Süreç boyunca çalışanın hakları korunur.

## İtiraz
Disiplin kararına, tebliğden itibaren 5 iş günü içinde İK'ya itiraz
edilebilir. İtiraz, karara katılmayan bir üst yönetici tarafından
değerlendirilir.""",
    },
    {
        "page_key": "ik-prim-politikasi",
        "space": "IK",
        "title": "Prim ve teşvik politikası",
        "restricted_to": "ik-yonetim",
        "content": """## Prim yapısı
Yıllık prim, şirket hedefi gerçekleşmesi ile bireysel performans katsayısının
çarpımıyla hesaplanır. Katsayılar ücret komitesince belirlenir ve gizli
tutulur.

## Ödeme
Primler performans dönemi kapanışını izleyen mart ayında ödenir. Prim oranları
ve bireysel katsayılar yalnız İK yönetimiyle paylaşılır.

## Özel durumlar
Yıl içinde ayrılan çalışanın primi orantılı hesaplanır; düşük performans notu
alan çalışana prim ödenmeyebilir. Bu kurallar maaş bandı bilgisiyle birlikte
gizlidir.""",
    },
    # --- Güvenlik / erişim kümesi (ENG) ---
    {
        "page_key": "eng-ag-erisim",
        "space": "ENG",
        "title": "Ağ erişim ve güvenlik duvarı",
        "restricted_to": None,
        "content": """## Ağ segmentleri
Kurumsal ağ üretim, kurumsal ve misafir olmak üzere ayrılır. Üretim ağına
yalnız yetkili mühendisler sıçrama sunucusu üzerinden erişir. Misafir ağı iç
kaynaklara kapalıdır.

## Güvenlik duvarı istekleri
Yeni port veya adres erişimi ağ değişiklik formuyla talep edilir ve güvenlik
onayından geçer. Geçici erişimler süre sonunda otomatik kapanır.

## Uzak erişim
Ofis dışından iç ağa erişim yalnız VPN ile mümkündür; bölünmüş tünel
kapalıdır. Yetkisiz cihazların bağlanması engellidir.""",
    },
    {
        "page_key": "eng-parola-politikasi",
        "space": "ENG",
        "title": "Parola ve kimlik doğrulama politikası",
        "restricted_to": None,
        "content": """## Parola kuralları
Kurumsal hesap parolaları en az 14 karakter olup büyük/küçük harf, rakam ve
sembol içerir. Parolalar 90 günde bir yenilenir ve son 5 parola tekrar
kullanılamaz.

## Çok faktörlü doğrulama
Tüm kritik sistemlerde çok faktörlü doğrulama (MFA) zorunludur. Kayıp cihazda
MFA sıfırlama, BT destek üzerinden kimlik doğrulamasıyla yapılır.

## Parola yöneticisi
Paylaşımlı hesap parolaları kurumsal parola kasasında tutulur; düz metin
paylaşım yasaktır. Servis hesaplarının parolaları otomatik döndürülür.""",
    },
    {
        "page_key": "eng-veri-siniflandirma",
        "space": "ENG",
        "title": "Veri sınıflandırma matrisi",
        "restricted_to": "guvenlik",
        "content": """## Sınıflandırma seviyeleri
Veriler herkese açık, iç kullanım, gizli ve çok gizli olarak sınıflandırılır.
Her belge sahibi tarafından etiketlenir; etiketsiz veri iç kullanım kabul
edilir.

## İşleme kuralları
Gizli ve çok gizli veri şifreli saklanır ve yalnız bilmesi gerekenlerle
paylaşılır. Çok gizli verinin dışa aktarımı güvenlik ekibi onayına tabidir.

## Gizli envanter
Sınıflandırma matrisi ve müşteri veri envanteri yalnız güvenlik ekibiyle
paylaşılır. Yanlış sınıflandırma veya sızıntı şüphesi güvenlik ekibine
bildirilir.""",
    },
    {
        "page_key": "eng-surumleme",
        "space": "ENG",
        "title": "Sürümleme ve dallanma modeli",
        "restricted_to": None,
        "content": """## Dallanma modeli
Ana dal her zaman dağıtılabilir tutulur. Özellikler kısa ömürlü dallarda
geliştirilir ve inceleme sonrası ana dala birleştirilir. Uzun ömürlü dal
tutulmaz.

## Sürüm numaralama
Sürümler anlamsal olarak numaralanır: kırıcı değişiklik ana, geriye uyumlu
özellik ikincil, düzeltme yama numarasını artırır. Her sürüm etiketlenir ve
sürüm notu yayımlanır.

## Etiket ve geri dönüş
Üretime çıkan her sürüm sürüm kontrol etiketiyle işaretlenir; hızlı geri dönüş
için bir önceki etiket her zaman hazır tutulur.""",
    },
    {
        "page_key": "eng-test-stratejisi",
        "space": "ENG",
        "title": "Test stratejisi ve kapsam",
        "restricted_to": None,
        "content": """## Test piramidi
Testler birim, entegrasyon ve uçtan uca olarak katmanlanır. Ağırlık hızlı ve
çok sayıda birim testtedir; uçtan uca testler kritik akışlarla sınırlı
tutulur.

## Kapsam eşiği
Yeni kodda birim test kapsamı en az %80 beklenir. Kapsamı düşüren
birleştirmeler incelemede işaretlenir. Kırık test ile üretime çıkılmaz.

## Test verisi
Testlerde gerçek müşteri verisi kullanılmaz; anonimleştirilmiş veya üretilmiş
veri kullanılır. Test ortamları üretimden yalıtılmıştır.""",
    },
    {
        "page_key": "eng-nobet",
        "space": "ENG",
        "title": "Nöbet ve eskalasyon düzeni",
        "restricted_to": None,
        "content": """## Nöbet düzeni
Üretim sistemleri için birincil ve ikincil nöbetçi mühendis haftalık dönüşümlü
atanır. Nöbet takvimi bir ay önceden yayımlanır; devir toplantısıyla teslim
edilir.

## Çağrı ve eskalasyon
Uyarı önce birincil nöbetçiye gider; 10 dakikada yanıt alınamazsa ikincil
nöbetçiye, ardından ekip yöneticisine yükselir. Eskalasyon zinciri olay
aracında tanımlıdır.

## Nöbet sonrası
Yoğun gece müdahalesi sonrası nöbetçiye telafi dinlenmesi verilir. Tekrarlayan
uyarılar, nöbet yükünü azaltmak için düzenli gözden geçirilir.""",
    },
    {
        "page_key": "eng-loglama",
        "space": "ENG",
        "title": "Loglama ve izleme standartları",
        "restricted_to": None,
        "content": """## Log standartları
Uygulamalar yapılandırılmış (JSON) log üretir; her kayıtta zaman damgası, önem
düzeyi ve izleme kimliği bulunur. Hassas veri loglara yazılmaz.

## Saklama
Loglar merkezi sistemde 30 gün, denetim logları 1 yıl saklanır. Erişim yetkiye
bağlıdır ve loglara erişim de loglanır.

## İzleme ve uyarı
Kritik hata oranı ve gecikme eşikleri uyarı üretir. Panolar hizmet başına
gecikme, hata ve doygunluğu gösterir; uyarılar nöbetçiye yönlendirilir.""",
    },
    {
        "page_key": "eng-erisim-yonetimi",
        "space": "ENG",
        "title": "Erişim yönetimi ve en az yetki",
        "restricted_to": None,
        "content": """## En az yetki
Sistem erişimleri görev gereğiyle sınırlıdır (en az yetki ilkesi). Yeni
erişim yönetici onayıyla talep edilir ve gerekçesi kaydedilir.

## Erişim gözden geçirme
Kritik sistem erişimleri üç ayda bir gözden geçirilir; gereksiz yetkiler
kaldırılır. Ayrılan çalışanın erişimleri son iş günü iptal edilir.

## Ayrıcalıklı hesaplar
Yönetici (admin) hesapları ayrı tutulur ve yalnız gerektiğinde yükseltmeyle
kullanılır. Ayrıcalıklı işlemler ek onay ve loglama gerektirir.""",
    },
    # --- Masraf / finans kümesi (FIN) ---
    {
        "page_key": "fin-seyahat",
        "space": "FIN",
        "title": "Seyahat ve harcırah esasları",
        "restricted_to": None,
        "content": """## Seyahat onayı
İş seyahatleri, tahmini bütçesiyle birlikte yöneticiden önceden onaylanır.
Uçuşlar ekonomi sınıfında planlanır; 6 saati aşan uçuşlarda business sınıfı
değerlendirilir.

## Harcırah
Konaklama ve günlük harcırah üst limitleri şehir bazında finans portalında
yayımlanır. Limit üstü harcamalar gerekçeyle finans onayına tabidir.

## Masraf birleştirme
Seyahat masrafları dönüşten sonra 15 gün içinde tek dosyada masraf sistemine
girilir. Fişsiz kalemler ödenmez; günlük harcırah için fiş aranmaz.""",
    },
    {
        "page_key": "fin-kurumsal-kart",
        "space": "FIN",
        "title": "Kurumsal kart kullanımı",
        "restricted_to": None,
        "content": """## Kart tahsisi
Sık masraf yapan pozisyonlara kurumsal kredi kartı tanımlanır. Kart yalnız iş
harcamalarında kullanılır; kişisel harcama yasaktır.

## Ekstre ve mutabakat
Kart harcamaları aylık ekstre ile masraf sistemine yansır; kart sahibi her
kalemi fiş yükleyerek onaylar. Onaylanmayan kalemler kişisel borç sayılır.

## Limit ve kayıp
Kart limitleri pozisyona göre belirlenir. Kayıp veya çalıntı kart, derhal
bankaya ve finansa bildirilerek bloke ettirilir.""",
    },
    {
        "page_key": "fin-fatura",
        "space": "FIN",
        "title": "Fatura kesim ve tahsilat",
        "restricted_to": None,
        "content": """## Fatura kesimi
Müşteriye kesilen faturalar sözleşme koşullarına göre finans tarafından
düzenlenir. Fatura talebi, teslim veya kabul belgesiyle birlikte finansa
iletilir.

## Tahsilat takibi
Vadesi geçen alacaklar finans tarafından takip edilir; 30 günü aşan
gecikmelerde hatırlatma, 60 günde eskalasyon uygulanır.

## Düzeltme ve iade
Hatalı faturalar iade faturasıyla düzeltilir. İptal ve iadeler muhasebe
onayından geçer ve kayıt altına alınır.""",
    },
    {
        "page_key": "fin-avans",
        "space": "FIN",
        "title": "Nakit avans süreci",
        "restricted_to": None,
        "content": """## Avans talebi
Öngörülen iş harcamaları için nakit avans talep edilebilir. Talep, gerekçe ve
tahmini tutarla yöneticiden onaylanır; avans kişinin sorumluluğundadır.

## Kapatma
Avans, harcama sonrası 15 gün içinde masraf beyanıyla kapatılır. Kullanılmayan
tutar iade edilir; kapatılmayan avans maaştan mahsup edilir.

## Sınırlar
Aynı anda açık en fazla bir avans bulunabilir. Önceki avansı kapatmayan
çalışana yeni avans verilmez.""",
    },
    {
        "page_key": "fin-raporlama",
        "space": "FIN",
        "title": "Finansal raporlama",
        "restricted_to": None,
        "content": """## Dönemsel raporlar
Aylık gelir-gider ve nakit akış raporları, takip eden ayın 10'una kadar
yayımlanır. Çeyrek kapanış raporları yönetim kuruluna sunulur.

## Bütçe gerçekleşme
Birim bazında bütçe-gerçekleşme farkı aylık raporlanır. Yüzde 10'u aşan
sapmalar gerekçelendirilir ve revizyon süreci başlatılır.

## Denetim
Yıllık bağımsız denetim öncesi mutabakatlar tamamlanır. Raporlama ilkeleri
yürürlükteki muhasebe standartlarıyla uyumludur.""",
    },
    {
        "page_key": "fin-vergi",
        "space": "FIN",
        "title": "Vergi ve belge düzeni",
        "restricted_to": None,
        "content": """## Vergi yükümlülükleri
Kurumlar vergisi, KDV ve stopaj beyannameleri yasal sürelerde verilir. Beyan
takvimi finans tarafından izlenir; gecikme cezaya yol açar.

## Belge düzeni
Gider belgelerinin vergi mevzuatına uygun olması gerekir; usulsüz belge gider
yazılamaz. Yurt dışı hizmet alımlarında stopaj değerlendirilir.

## Teşvikler
Ar-Ge ve yatırım teşviklerinden yararlanma finans tarafından yürütülür; ilgili
harcamalar ayrı kodlanır ve belgelenir.""",
    },
    {
        "page_key": "fin-bordro",
        "space": "FIN",
        "title": "Bordro ve maaş ödemeleri",
        "restricted_to": "fin-yonetim",
        "content": """## Bordro süreci
Aylık bordro; mesai, izin ve kesinti verileriyle finans tarafından hazırlanır
ve ayın son iş günü ödenir. Bordro verileri gizlidir.

## Kesintiler
Vergi, sigorta ve yasal kesintiler bordroda gösterilir. Bireysel maaş ve
kesinti bilgileri yalnız finans yönetimi ve ilgili çalışanla paylaşılır.

## Gizlilik
Çalışan bazlı maaş, prim ve ödeme bilgileri kişiye özeldir; toplu bordro
dökümüne yalnız finans yönetimi erişebilir.""",
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
