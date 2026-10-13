# Technical overview — operational verification pipeline  
**Distribution:** NDA / Enterprise & Market Alpha only · **Classification:** Confidential · **No formulas**

Bu belge, müşteri due diligence süreçleri için **iş akışı ve güven kontrollerinin** özetidir. **Matematiksel formül, eşik değerleri veya kaynak kod parametreleri içermez**; bunlar ticari sıfatlı çerçevede veya ayrı teknik ek sürecinde paylaşılabilir.

---

## 1. Scope

Kapsam: sabit AOI üzerinde **Landsat Collection 2 Level-2 termal** bileşeni ile **Sentinel-5P troposferik NO₂** (birleşik L3 çizgisi) ile uyumlu özet üretimi ve rapor şablonlarına basım.

---

## 2. Processing topology

1. **Kimlik ve proje:** Üretim ortamında Earth Engine proje kimliği ve erişim politikaları kurumsal olarak yönetilir.
2. **AOI oluşturma:** POI + müşteriyle sabitlenmiş tampon politikası; geometri sürümü rapor meta verisinde yer alır.
3. **Zaman seçimi:** Talep edilen pencere; bulut örtüsü ve QA nedeniyle gözlemlenebilirlik raporda metinsel olarak işlenir.
4. **Termal bileşik:** LC08/LC09 uyumlu koleksiyon birleştirmesi ve QA tabanlı maskeleme ile bileşik özet; çıktı °C ölçekli bir üst sınır/özet gösterge olarak rapora yazılır (politika sürümü kayıtlıdır).
5. **NO₂ özeti:** AOI içinde zamanda ortalama troposferik sütun (mol/m²); ürün seviyesi ve QA yaklaşımı üretim kodu ile tek kaynak olmalıdır.
6. **Rapor üretimi:** Şablon doldurma, mühür bölümü ve otomatik feragat snippet’i; PDF rasterization müşteri ortamında pandoc/LaTeX veya eşdeğer araçlarla yapılabilir.
7. **Dashboard:** Ayrıştırılmış Markdown çıktılarından tablo ve harita katmanları; kapasite yüzdesi göstergesi dahili ölçekleyiciye bağlıdır *(parametreler kamuya açık dokümanda yer almaz)*.

---

## 3. Governance & audit trail

- Metodoloji ana referans: `docs/turkiye/cco-audit-methodology.md`
- Sürüm kontrolü: rapor üretim tarihi ve mümkün olduğunda koleksiyon / ürün etiketleri
- **CCO mührü:** Hukuki uygunluk değil; operasyonel doğrulama ve şeffaflık çerçevesi

---

## 4. Security & data handling

- Ham görüntü indirimi müşteri SLA’sına göre sınırlı veya **yalnız görselleştirme katmanı** olarak sunulabilir.
- API katmanında kimlik doğrulama ve oran sınırları kurumsal politikaya tabidir *(bu dosya implementasyon içermez)*.

---

## 5. SLA başlıkları (örnek müzakere maddeleri)

- Veri tazeliği ve yeniden çalıştırma penceresi  
- Anomali uyarısı teslim kanalı (kurumsal paket)  
- Destek ve eskalasyon iletişimi  

*(Sayısal SLA burada verilmez; kontratta tanımlanır.)*
