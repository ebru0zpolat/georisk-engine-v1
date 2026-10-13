# Claude Design brief'leri — GeoRisk konsolu

Claude Design repoyu görmüyor. Bu yüzden sistem değerleri **bir kez, ilk prompt'ta**
verilir ve **aynı sohbette** devam edilir; her ekranı yeni sohbette istemeyin.

Sıra önemli: 1 gönderilmeden 2–6 anlamsız olur.

---

## 0 · Nasıl çalıştırılır

- Her prompt'u **ayrı** gönder. "Hepsini birden çiz" deme — altı ekranı tek turda
  isteyince hiçbiri bitmiyor.
- İlk tur ekran değil, **tasarım sistemi**. Bu, sonraki her turun dayanağı.
- Düzeltirken **"sadece şunu değiştir, gerisine dokunma"** de.
- Beğendiğin ekrandan sonra bir sonraki prompt'a *"önceki ekranın stilini birebir
  koru"* diye başla.
- Bir bölümü eleştirmek yerine ne olması gerektiğini yaz:
  "kapsam rakamı tıklanabilir görünsün" > "kapsam bandı kötü olmuş".

---

## 1 · Tasarım sistemi

```text
GeoRisk Engine adlı kurumsal bir iklim riski platformu için konsol arayüzü
tasarlayacağız. Kullanıcı: banka ve sigorta şirketlerindeki kredi/risk analistleri.
Ürün, varlık konumlarını fiziksel iklim riskine ve beklenen finansal kayba çeviriyor
ve her sayının kaynağını denetlenebilir kılıyor.

Önce tasarım sistemini kur. Aşağıdaki değerleri BİREBİR kullan; yeni renk veya font
uydurma.

Yüzeyler
  #0a1628  sayfa zemini (ink)
  #131f33  panel / kart
  #101a2b  inset / koyu zemin
  #22304a  kenarlık
  #3b4d68  vurgulu kenarlık

Metin
  #e6edf5  gövde
  #9aa8ba  ikincil

Üç aile + nötr — bunlar aksan değil, anlam taşır. Dördüncü bir hue açma.
  teal     #2ec990 (400) · #5dcaa5 (300)
  amber    #ef9f27 (500) ve tint'i
  kırmızı  #e24b4a (500) ve tint'i
  nötr     #c3cedb (açık) · #9aa8ba (orta)

  tint  = metin ailenin 500'ü, kenarlık alfa 0.28, zemin alfa 0.10
  solid = aynı metin, kenarlık alfa 0.6

Tipografi
  Inter.
  Başlıklar 800 ağırlık, tracking -0.02em.
  Gövde 400/500.
  Sayı, kimlik, hash ve rozet metni tabular figürlerle.

Ölçüler
  Panel radius 12px, kontrol radius 8–10px, rozet radius 4px
  Kontrol yüksekliği masaüstünde 36px, dokunmalı yüzeylerde en az 44px
  Panel iç boşluğu 18–22px

Bu turda ekran çizme. Tek bir stil sayfası artboard'u üret:
renk swatch'ları, tip rampası, buton / giriş / rozet / tablo satırı örnekleri,
sayı biçimleri (₺1,284,400 · 1.52% · 0.148 · sha256:4b1e…3a51 · 2026-08-30 09:14Z),
ve beş durum deseni: empty, loading, error, partial-success, degraded.
Son ikisi HATA DEĞİL — hatadan görsel olarak ayrılmalılar.
```

---

## 2 · Trust chip sistemi

```text
Aynı sistemle devam. Şimdi ürünün en kritik bileşenini tasarla: trust chip.

Bu üründe hiçbir sayı, kaynağı görünmeden gösterilemez. Chip bunu taşıyan atom.

Anatomi: 8px durum noktası + durum adı (DM Mono 11px, koddaki string ile birebir
aynı) + 1px kenarlık + radius 4px + padding 3px 8px. Zemin, durum renginin
%8–10 alfası.

Dokuz durum, dört aile. Renkler sabit:

  teal     VERIFIED      #2ec990 solid  kaynak doğrulandı, lisans incelendi
           LIVE          #5dcaa5 solid  gerçek connector yanıtı, bu çalıştırmada alındı
  amber    FIXTURE       #ef9f27 tint   deterministik test verisi
           SYNTHETIC     #ef9f27 solid  etiketli sentetik hasar eğrisi
  kırmızı  DEGRADED      #e24b4a tint   birincil kaynak düştü, yedek yolla üretildi
           NOT_ELIGIBLE  #e24b4a solid  karar amaçlı kullanılamaz
  nötr     MODELLED      #c3cedb        modelden çıktı, ölçüm değil
           DERIVED       #9aa8ba        başka değerlerden hesaplandı
           STALE         #9aa8ba        güncel çalıştırmadan gelmiyor
                         + kap: zemin #101a2b, kenar #3b4d68

Aile hue'su durumu değil SINIFI anlatır; adım, sınıf içindeki şiddeti.

İKİ EKSEN, İKİ YUVA — bu en kritik kural:
  VERIFIED / LIVE / FIXTURE / SYNTHETIC  "girdi nereden geldi"
  MODELLED / DERIVED / STALE             "değer girdisinden ne kadar uzak ve ne kadar eski"
Bir değer aynı anda LIVE ve STALE olabilir. Bu ikisi aynı yuvada yarışmaz:
kaynak yuvası solda, türetme yuvası sağda, sabit sırayla.

STALE metin eki taşır: "STALE · 14d". Kap farkı (koyu zemin + parlak kenar) tek
başına yetmiyor — rapora küçültülerek yapıştırılan ekran görüntüsünde kayboluyor.

Üç yerleşim ölçeğini göster:
  1. Değer seviyesi — sayının yanında (örnek: ₺1,284,400 + SYNTHETIC + DERIVED)
  2. Bölüm seviyesi — bölüm başlığıyla aynı hizada, bölümün EN ZAYIF değeri
  3. Sayfa seviyesi — kapatılamayan üst bant; yalnızca NOT_ELIGIBLE buraya çıkar

Sayfa bandı örneği:
"Demonstration output. Not for credit, pricing or disclosure decisions."

Bir de "yapılmayacaklar" bölümü ekle:
chip'i tooltip arkasına saklamak; sentetik değeri "tahmin" veya "modelled" gibi
yumuşatılmış bir kelimeyle etiketlemek; durumu yalnız renkle anlatmak;
iki ekseni tek yuvaya sıkıştırmak.
```

---

## 3 · Portfolio upload & triage

```text
Aynı sistemle bir masaüstü ekranı çiz: Portfolio upload & triage, 1360px genişlik.

Amaç: analist 120 satırlık bir portföy CSV'si yüklüyor, 87'si analiz ediliyor.
Bu ekranın tek işi kalan 33'ün ne olduğunu görünür kılmak. Hiçbir satır sessizce
düşmez.

Üstten aşağı:

- Uygulama üst çubuğu: marka, Portfolios / Assets / Evidence / Reports sekmeleri,
  aktif country pack rozetleri (pack-tr v0.4 · pack-nl v0.2)

- Kapatılamaz kırmızı bant: NOT_ELIGIBLE chip'i +
  "Demonstration output. Not for credit, pricing or disclosure decisions." +
  altında "Damage curves are labelled synthetic v0.x."

- Beş adımlı ray: Upload → Hazard → Expected loss → Adaptation → Avoided loss
  (Upload aktif)

- "Portfolio upload" paneli, yan yana üç kart:
  1. File — valuation date 2026-01-01, display currency TRY,
     limitler: 500 satır / 10 MB / CSV-XLSX
  2. Column mapping — lat→latitude, lon→longitude, teminat_deger→asset_value,
     yapi_tipi→structure_type (ONAY BEKLİYOR, amber vurgulu), notlar→ignored.
     "Confirm mapping" butonu.
  3. Row validation — Valid rows 87 / Needs attention 33, iki renkli ilerleme
     çubuğu, "Run analysis" butonu (mapping onaylanana kadar pasif)

- Kapsam bandı: "87 of 120 assets analysed · 33 excluded" ve "Show the 33"
  bağlantısı. Bu rakam TIKLANABİLİR görünmeli — alıcının ilk sorduğu şey bu.
  Yanında: "Portfolio EAL covers analysed assets only."

- Triyaj tablosu. Filtre chip'leri: All 33 · Geocode failed 18 · No country pack 9 ·
  Missing value 4 · Invalid coordinate 2.
  Kolonlar: Row · Asset id · Reason (chip + açıklama) · Offending value · Fix.
  Örnek satırlar:
    14 · TSKB-0142 · geocode-failed · "Organize San. Blg. 4. Cd." · Enter coordinates
    27 · TSKB-0155 · no-country-pack · country = "BG" · Not fixable — no pack
    31 · TSKB-0159 · missing-value · teminat_deger = "" · Enter value
    48 · TSKB-0176 · invalid-coordinate · lat = 91.4 · Correct coordinate
  Düzeltilebilir satırların Fix hücresi aksiyon renginde, düzeltilemeyenler soluk.

- Sağ üstte "Export CSV" ve "Re-run with fixes".

Lorem ipsum kullanma; yukarıdaki gerçek örnek veriyi kullan.
```

---

## 4 · Asset detail

```text
Aynı sistemle ikinci masaüstü ekranı: Asset detail, 1360px.

Amaç: tek bir varlık için "bu sayıya nasıl varıldı" sorusunu cevaplamak.

Örnek varlık: Antalya Kepez Logistics Depot · TSKB-0034 · Commercial, warehouse ·
36.9081, 30.6956 · varlık değeri ₺84,500,000 · risk bandı HIGH.

- Breadcrumb: TSKB_CRE_2026Q1 › TSKB-0034
- Başlık, sağda risk bandı hapı (HIGH · band 3 of 4) ve SYNTHETIC chip'i
- Kontrol şeridi: Horizon segmenti (Today / 2030 / 2050) + SSP2-4.5 rozeti +
  "Adaptation" aç/kapa anahtarı

- Beş kartlık şelale, soldan sağa:
  1 Hazard — 0.62 — "Composite flood intensity, SSP2-4.5" — LIVE
  2 Vulnerability — MDR 0.148 — "Warehouse curve, pack-tr" — SYNTHETIC
  3 Expected loss — ₺1,284,400 — "EAL · 1.52% of asset value" — SYNTHETIC
    (vurgulu kart)
  4 Adaptation — "Perimeter barrier" — CAPEX ₺2,100,000, life 25y — FIXTURE
  5 Avoided loss — ₺892,000/yr — "Residual EAL ₺392,400 · payback 2.4y" —
    SYNTHETIC
  Adaptation anahtarı kapalıyken 4 ve 5 soluk görünmeli.

- Horizon karşılaştırma: üç kart —
  Today ₺1,284,400 (1.52% of value) · 2030 ₺1,613,000 (+25.6%) ·
  2050 ₺2,241,000 (+74.5%) — altlarında oransal barlar, seçili olan vurgulu.

- Konum bağlamı haritası: yükseklik bantları, varlık pini, legend. Altında:
  "Elevation is shown as terrain context. It is not a flood probability and not a
  loss estimate."

- Sağ kolon:
  Evidence kartı — audit_id aud_9f3c1ba7e204, model_version risk-v0.9.2,
  methodology v0.3.1, "Open evidence" ve "JSON" butonları.
  Risk drivers — Pluvial flood 0.78, Extreme heat 0.54, Coastal surge 0.31,
  Wildfire 0.19, Water stress 0.44 (yatay barlar, değere göre renk).
```

---

## 5 · Evidence / audit viewer

```text
Aynı sistemle üçüncü masaüstü ekranı: Evidence / audit viewer, 1360px.

Amaç: bir audit_id ile gelen denetçiye, sonucu yeniden üretmek için gereken her
referansı vermek. Regüle alıcıya ürünün farkını anlatan tek ekran bu.

- Başlık bloğu: "Evidence record" etiketi, DM Mono ile büyük aud_9f3c1ba7e204,
  yanında VERIFIED / SYNTHETIC / NOT_ELIGIBLE chip'leri,
  "Generated 2026-08-30 09:14Z · retained until 2033-08-30".
  Sağda: Evidence JSON · PDF report · Back to result.

- Üç sekme: What produced it · Source manifest · Limitations

- What produced it: model_version risk-v0.9.2 · methodology v0.3.1 ·
  country pack pack-tr v0.4 · source commit 36f84f4.
  Altında Integrity: request hash, response hash, previous link
  (aud_71ba0c4de118 · 2026-08-29 16:02Z). Tam sha256 değerleri görünsün,
  kopyalanabilir dursun, yanlarında verified / linked rozeti olsun.

- Source manifest tablosu — Source · Version · Retrieved · Licence · State · Used for:
    Copernicus ERA5-Land · 2026.06 · LIVE · Hazard
    CDS ORAS5 (Zarr) · v5.1 · LIVE · Hazard
    AHN elevation (NL) · AHN4 · FIXTURE · Context only
    pack-tr damage curves · v0.4 · SYNTHETIC · Vulnerability
    Google Earth Engine · — · DEGRADED · Hazard
    WRI Aqueduct flood · 4.0 · BLOCKED · "Licence unreviewed" · Not used
  Son satır kırmızı tonda. Satıra tıklayınca endpoint, spatial bounds, payload hash
  ve kısa bir not açılsın.
  Altına: "A blocked source never reaches a conclusion. It is listed here so its
  absence is visible rather than invisible."

- Limitations: üç kart —
  "Not a flood probability" · "Not calibrated to observed loss" ·
  "Not a compliance determination".
  Bunlar dipnot değil, kanıtın parçası; o ağırlıkta görünsünler.
```

---

## 6 · İki mobil ekran

```text
Aynı sistemle iki mobil ekran, 390×844.

1) Asset snapshot — salt-okunur
  Üst çubuk: geri oku + "Antalya Kepez Depot" + "TSKB-0034 · read-only"
  Kapatılamaz NOT_ELIGIBLE bandı (mobilde de düşmez)
  Hero kart: risk bandı hapı + SYNTHETIC chip'i +
    "Expected annual loss" ₺1,284,400 + "1.52% of asset value"
  Horizon segmenti (Today / 2030 / 2050), 44px yükseklik
  Katman özeti: Hazard 0.62 · Vulnerability MDR 0.148 ·
    Adaptation Perimeter barrier · Avoided loss ₺892,000/yr
  Top drivers: üç yatay bar
  Evidence satırı: aud_9f3c1ba7e204 → chevron
  Altta: "Bu görünüm salt-okunur. Düzeltme ve yeniden çalıştırma masaüstünde yapılır."

2) Field triage
  Üst çubuk: "Field triage" + portföy adı + sağda "queued · 3 offline" rozeti
  İlerleme: "Geocode failures assigned to you" · "3 / 18 fixed" · bar
  Varlık kartı: TSKB-0142 · geocode-failed chip'i · adres · sebep
  Harita: koordinat yokken boş ("Henüz koordinat yok"), yakalandığında pin
  Koordinat bloğu: 36.90814, 30.69557 · doğruluk ±4 m ·
    "Bulunduğum konumu kullan" butonu (48px)
  "Fotoğraf ekle" satırı (56px, thumbnail yeri)
  "Onayla ve sıradakine geç" birincil buton (48px)
  Altta: "Düzeltme cihazda kuyruğa alınır ve bağlantı gelince senkronlanır."

İkisinde de: sahte iOS durum çubuğu veya sahte klavye ÇİZME — gerçek cihazda
işletim sistemi bunları kendi çiziyor, çizilmiş olan üstüne biniyor.
Dokunma hedefleri en az 44px.
```

---

## Açık kalan iki durum

Eski yedilik sözlükteki iki durum yeni dokuzlukta karşılıksız kaldı; brief'lerde
`BLOCKED` olarak geçiyor ama ailesi belirsiz:

- **`blocked`** — kaynak sonuca giremedi. Manifest satırında hâlâ gerekli.
  Kırmızı ailenin üçüncü adımı mı, yoksa chip değil satır durumu mu?
- **`not-validated`** — bu kullanım için ampirik doğrulama yok.
  `NOT_ELIGIBLE` içine mi katlanıyor, yoksa sayfa bandında ikinci chip olarak mı kalıyor?

Bu ikisi cevaplanmadan claim-control testi yazılamaz — kendi kuralımız gereği
sözlük büyüdüğünde önce test güncellenir.
