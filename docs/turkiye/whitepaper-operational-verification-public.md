# GeoRisk Engine — Operational Verification Whitepaper (Public)

**Version:** 1.3 · **Audience:** Investors, sustainability desks, technical diligence readers · **Classification:** Public  

Bu kamuya açık özet, **uydu kaynaklı operasyonel doğrulama** çizgisinin genel hatlarını sunar. Tam maske politikası, ürün sürümü ve feragat için tek kaynak: **[cco-audit-methodology.md](./cco-audit-methodology.md)**.

---

## Executive summary

GeoRisk Engine, sabit bir AOI üzerinde **Landsat** yüzey sıcaklığı proxy’si ile **Sentinel-5P** troposferik NO₂ sütununu birlikte okuyarak endüstriyel varlıklarda **operasyonel şeffaflık** sağlar. Çıktılar **CCO hizası mühürlü** rapor ve dashboard bileşenleri ile teslim edilir; üretim tonajı veya düzenleyici uygunluk **otomatik olarak ispatlanmış sayılmaz**.

Trafo üretimi gibi **düşük termal kontrast** beklenen tesislerde kamuya açık çerçeve, **NO₂ / CO / gece ışığı** ile lojistik bağlamını okuyan emisyon–aktivite hattını özetler (**Bölüm 3**); sevkiyat yoğunluğundan kapasiteye giden **katsayılar proprietary** kalır (**Bölüm 3.4** ve ilgili repo beyanı).

**Sürdürülebilirlik raporları ve Yeşil Mutabakat bağlamı:** Kurumsal sürdürülebilirlik raporlarındaki **karbon ayak izi beyanları**, sahada ölçüm ağı olmadan tek başına denetlenmekte zorlanabilir. GeoRisk üretim hattı, beyanlarla **uydu türevli NO₂ ve CO (ve ilgili sektörlerde ek proxy’ler)** özetlerini **operasyonel olarak çok kısa gecikmeyle** yan yana getirerek, finans ve sürdürülebilirlik ekiplerine **bağımsız bir “üçüncü taraf perspektifi”** (uydu tabanlı çapraz soru) sunar; bu süreç **hesaplama ve rapor üretimi** açısından tipik olarak saniyeler–dakikalar ölçeğindedir, veri erişimi ve EE kota gibi dış faktörlere tabidir. Bu çıktı **Avrupa Yeşil Mutabakatı** kapsamındaki şeffaflık ve denetlenebilirlik beklentileriyle **uyumlu bir hazırlık / iç kontrol** aracı olarak konumlandırılabilir; **resmi uygunluk onayı, düzenleyici mühür veya “kesin doğrulama”** anlamına gelmez (**Bölüm 4**).

---

## 1. Veri edinimi ve spektral analiz

Sistem, küresel uydu takımı verilerini kullanarak tesislerin **termal** ve **emisyon imzalarını** özetler (spectral bands üzerinden türetilmiş ürün katmanları).

### 1.1 Termal katman

- **Kaynak:** Landsat 8 ve 9, **Collection 2 Tier 1 Level-2** ürünleri; yüzey sıcaklığı bileşeni (**ST_B10** üzerinden °C ölçekli özet).
- **Raporlama çözünürlüğü:** Dashboard ve raporlarda sıcaklık çoğunlukla **ondalık basamaklı** sunulur; bu, çıktının **görüntülenme çözünürlüğüdür**. Atmosferik düzeltme, emissivity ve karıştırıcı kaynaklar nedeniyle **tekil piksel düzeyinde termometrik doğruluk** sahada doğrulanmadan genellenmez.

### 1.2 Emisyon katmanı

- **Kaynak:** Sentinel-5P **OFFL** iş hattı ile uyumlu **L3** birleşik troposferik NO₂ ürünleri.
- **Rol:** Troposferik NO₂ sütunu yoğunluğu (**mol/m²**), operasyonel hareketliliğin **ikincil kanıtı / bağlam sinyali** olarak kullanılır; tek başına kaynak ayırımı yapmaz.

### 1.3 Ön işleme ve kalite (QA)

- **Landsat:** **QA_PIXEL** türevli politikalarla bulut, gölge ve üretimde tanımlı sorunlu sınıflar maskelenir; duman veya aerosol senaryoları **bağlamsal olarak** yorumlanır ve tam otomatik ayrıştırma iddiası taşımaz.
- **Sentinel-5P:** L3 çizgisinde kalite ve kesir politikası **L2 akışından farklıdır**; raporda kullanılan band ve kesir **tek kaynak** olarak yazılır.

### 1.4 AOI ve tekrarlanabilirlik

- **POI + tampon:** Termal taraf için tipik olarak **500 m** tampon ile karşılaştırılabilirlik; NO₂ için üretimde tanımlı ayrı tampon kullanılabilir.
- **CCO mührü:** Yapılandırılmış rapor gövdesi ve otomatik feragat snippet’leri ile teslim; **hukuki uygunluk taahhüdü değildir**.

---

## 2. Kapasite proxy tahmin modeli

**Tahmini Üretim Kapasitesi**, sahada ölçülen üretim hacminin **doğrudan ölçümü değildir**; Landsat türevli termal özetin, kuruluş içi tanımlı bir referans düzenine göre **yüzde ölçekli bir proxy** olarak sunulmasıdır.

### 2.1 Baz çizgisi ve kalibrasyon perspektifi

- **Kurumsal hedef:** Her tesis için, tarihsel olarak **yüksek operasyonel uygunluk** görülen dönemler referans alınarak baz çizgisi politikası oluşturulabilir (kalibrasyon ve saha doğrulaması ile).
- **Demo üretim hattı:** Kamuya açık kod yolunda basit bir doğrusal ölçekleyici örnek bulunur; **kurumsal kalibrasyon**, müşteri ve saha verisi ile **Proprietary Methodology** çerçevesinde yönetilir.

### 2.2 Çok katmanlı analiz (yol haritası)

- Anlık ısı imzası; tesise özel AOI; NO₂ bağlamı ve (kurumsal pakette) ek kalite bayrakları **birlikte** okunur.
- İleri seviye modeller (çok regresyonlu veya sektör içi bench karşılaştırması) **ürün yol haritası** kapsamında değerlendirilir; kamuya açık whitepaper **iç katsayıları veya normalizasyon denklemlerini içermez**.

### 2.3 Gizlilik ve mülkiyet

Regresyon katsayıları, normalizasyon politikası ve müşteriye özel kalibrasyon paketleri **Proprietary Methodology (ticari sır)** kapsamında yönetilir. Metodoloji mülkiyet ve sorumluluk çerçevesi: **[proprietary-thermal-capacity-proxy.md](./proprietary-thermal-capacity-proxy.md)**.

---

## 3. Trafo üretimi: emisyon ve aktivite tabanlı doğrulama (bilimsel çerçeve, public)

Çimento gibi **yüksek termal imza** beklenmeyen tesislerde (ör. trafo üretimi), operasyonel şeffaflık çizgisi **tek başına yüzey sıcaklığı** yerine **atmosferik emisyon ve gece ışığı** türevli göstergelere dayalı bir **kanıt üçgeni** ile kurulur. Bu bölüm, kamuya açık düzeyde **neden bu sinyallerin anlamlı bağlam sağlayabileceğini** özetler; **kaynak ayırımı, kapasite yüzdesi veya regülasyon uygunluğu** iddiası taşımaz.

### 3.1 Termal tek başına neden yetersiz kalabilir?

Büyük güç transformatörleri üretiminde, fırın tipi süreçlere kıyasla **AOI üzerinde tekil, stabil ve yüksek kontrastlı bir termal imza** her zaman beklenmez. Bu nedenle doğrulama mimarisi, tesis çevresindeki **kimyasal emisyon sütunları** ve **antropojenik gece aydınlatması** ile **lojistik yoğunluğu**nu bağlamsal olarak okumayı hedefler.

### 3.2 NO₂ sütunu: dolaylı enerji ve yoğun hareketlilik bağlamı

Troposferik **NO₂** sütun yoğunluğu, endüstriyel elektrik kullanımı ve yakıt tüketimine bağlı oksitleme süreçleri ile, ayrıca **ağır yük taşımacılığı** kaynaklı motor emisyonları ile **korelasyon gösterebilir**; ancak sinyal **bölgesel arka plan**, meteoroloji ve çoklu kaynak karışımı altında **belirsizlik taşır**. Public ürün hattında NO₂, **Scope 2 (dolaylı enerji)** beyanlarını “otomatik ispat” etmek için değil, **uydu ile çapraz sorulabilir bir bağlam katmanı** olarak konumlanır.

### 3.3 CO ve gece ışığı: ek kanıt katmanları

- **CO (Sentinel-5P ürün ailesi):** Yanma veya ısıl işlem çıktılarına duyarlı bir **ikincil emisyon göstergesi** olarak düşünülebilir; trafo üretim hatlarında proses özgü kullanım **tesis ve reçeteye göre değişir**, genel şema **kesin kaynak etiketi** vermez.  
- **VIIRS gece ışığı (DNB türevleri):** Aylık bileşiklerde sunulan **ortalama radyans**, vardiya / aydınlatma yoğunluğu ile **operasyonel mesai proxy’si** olarak yorumlanabilir; sıfır radyans her zaman “kapalı tesis” anlamına gelmez (bulut örtüsü, ürün sürüm notları ve `cf_cvg` gibi kalite boyutları metodoloji dosyasında ele alınır).

### 3.4 Kapasite ve sevkiyat skorları: proprietary sınır

Trafo **sevkiyat yoğunluğunu** çoklu uydu göstergelerinden **tek bir kapasite veya faaliyet yüzdesi**ne dönüştüren **katsayılar, ağırlıklar ve kalibrasyon paketleri** çimento hattındaki termal proxy ile aynı disiplinde **ticari sır** olarak kalır; kamu whitepaper bu denklemleri içermez. Mülkiyet ve sınıflandırma: **[proprietary-transformer-logistics-capacity-proxy.md](./proprietary-transformer-logistics-capacity-proxy.md)**.

---

## 4. Sınırlamalar ve feragatname

- Bu model **saha sensörlerinin yerine geçmez**; kesintisiz emisyon izleme veya üretim sayaçları ile **birebir ikame** garantisi verilmez.
- **Korelasyon:** Uydu proxy’sinin zemin gerçeği ile ilişkisi **tesis, mevsim ve karıştırıcılara göre değişir**. Kamuya açık olarak **sabit bir “%90+ korelasyon” oranı iddia edilmez**; böyle bir iddia ancak **tesise özel doğrulama çalışması** ile desteklenebilir.
- **Örnek gösterge:** Akçansa Çanakkale için iletişimde **≈%83.2** veya üretim çıktısında **%83.17** gibi değerler **istatistiksel / model tahminidir**; resmi finansal beyan, kapasite raporu veya düzenleyici tablo **yerine geçmez**.
- **Yatırım ve hukuki kullanım:** Çıktılar **yatırım tavsiyesi değildir**; tek başına mahkeme delili veya uygunluk beyanı oluşturmaz.

---

## Further reading (repository)

- Birleşik metodoloji: [cco-audit-methodology.md](./cco-audit-methodology.md)  
- Ürün / abonelik çerçevesi: [golden-standard-subscription-and-analytics.md](./golden-standard-subscription-and-analytics.md)  
- Trafo hattı — proprietary (sevkiyat / kapasite katsayıları): [proprietary-transformer-logistics-capacity-proxy.md](./proprietary-transformer-logistics-capacity-proxy.md)  
- Mühürlü operasyonel endeks, kapalı devre yayın ve QOR: [georisk-sealed-index-closed-loop-publishing.md](./georisk-sealed-index-closed-loop-publishing.md)  
- Birincil sektör öncelikleri (SKDM): [sectors-skdm-primary-priorities.md](./sectors-skdm-primary-priorities.md)  
- Due diligence (NDA): `docs/turkiye/due-diligence/` *(Market Alpha ve Institutional)*  
