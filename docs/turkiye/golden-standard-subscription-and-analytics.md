# Altın standardı, analitik yol haritası ve abonelik katmanları

Bu not, **abonelik modelinde müşteriye süreklilik ve karşılaştırılabilirlik** taahhüdü ile uyumlu veri sunumu, **finansal anlamlandırma** yönündeki araştırma çerçevesi ve **fiyatlandırma katmanları** için ortak dil oluşturur. Hukuki feragat ve teknik maskeleme ayrıntıları için önce **[cco-audit-methodology.md](./cco-audit-methodology.md)** esas alınmalıdır.

**Alternatif veri (Alternative Data)** çerçevesinde: ürün, yalnızca ham erişimi değil; operasyonel **mühür**, metodolojik **şeffaflık** ve sektör içi **karşılaştırılabilirlik** ile birlikte sunulan **nadir** bir sinyal paketidir. Fiyatlandırma mimarisi, bu sinyalin **finansal tahminleme ile kullanılabilirliğini** (ör. termal proxy üzerinden **Tahmini Üretim Kapasitesi**) merkeze alır — yine de çıktılar **yatırım tavsiyesi veya resmi beyan değildir**.

**CCO / kurumsal güven perspektifi:** Fiyat, sadece “veri indirme hakkı” değil; müşterinin satın aldığı **güven** (metodoloji tutarlılığı, mühür, feragat disiplini) ve **hız** (güncel dashboard, API, anomali uyarısı) avantajını da yansıtmalıdır.

---

## 1. Veri seti standardizasyonu (Altın standard)

| İlke | Gereksinim | Uygulama notu |
|------|------------|----------------|
| **Zaman damgası ve periyot** | Her tesis için ayda en az bir kez; bulutluluk oranının tanımlı eşiğin (ör. %10) altında olduğu **Altın Gözlem** penceresi seçimi ve raporda periyot açıklaması | Landsat revisit ve bulutluluk nedeniyle pencereler tesisten tesise kayabilir; seçilen tarih aralığı ve QA politikası raporda ve kod sürümünde sabitlenmelidir. |
| **Birim standardı (SI)** | Sıcaklık her zaman **°C**; troposferik NO₂ sütunu **mol/m²**. Landsat **Collection 2 Level-2** ve Sentinel-5P **L3** ürün seçimi korunmalıdır | Üretim hattı şu an LC08/LC09 C2 L2 (`ST_B10`) ve EE’de tipik L3 NO₂ bandı ile uyumludur; band/koleksiyon değişikliği sürüm notuna yazılır. |
| **Tampon (buffer) ve AOI sabitliği** | Tesisler arası **karşılaştırılabilirlik** için AOI politikası kurumsal olarak sabitlenmelidir | Varsayılan betiklerde termal AOI için **500 m** tampon kullanılır; NO₂ için ayrı tampon (ör. **2000 m**) plüm/ölçek farkı nedeniyle tanımlıdır. **Tamamen 500 m tek tampon** hedefi için ürün kararı ve metodoloji güncellemesi gerekir. |
| **Metodolojik şeffaflık** | Her veri seti, maskeleme ve hata payları için **cco-audit-methodology.md** ile tutarlı referans taşır | Rapor gövdeleri ve otomatik dipnotlar bu dosyaya bağlanır; yatırım/regülasyon iddiası taşımaz. |

---

## 2. Finansal tahminlere dönüştürme (predictive analytics — çerçeve)

Bu bölüm **ürün/yol haritası** niteliğindedir; otomatik fiyatlama veya yatırım tavsiyesi üretimi **teklif edilmez**. Calibrasyon saha verisi ve kurumsal model onayı olmadan katsayılar genellenemez.

### 2.1 Termal bazlı üretim tahmini (Kapasite kullanım proxy’si)

- **Fikir:** Yatırımcı için sıcaklık tek başına değil; **Kapasite Kullanım Oranı (KKO)** ile ilişkilendirilmiş bir **proxy** olarak konumlanır.
- **Baz çizgisi (baseline):** Tesisin “tam kapasiteye yakın” bilinen bir döneme ait termal özeti (ör. referans °C) **%100 aktivite** referansı olarak sabitlenir (tesis içi karar).
- **Delta analizi:** Referansa göre düşüşler, **operasyonel yavaşlama olasılığı** için tanımlanan kurumsal katsayı ile ölçeklenir (ör. °C başına %X); katsayılar **tesis ve sezon bazında kalibre** edilmelidir.
- **Örnek doğrusal proxy (demo):** `app/scoring/capacity_proxy.py` içindeki `estimate_capacity`: 15 °C altı ~%0, Çimsa Afyon referansı **20.11 °C → ~%100** (Streamlit panelinde **Tahmini Üretim Kapasitesi** sütunu ve grafik).

### 2.2 Emisyon bazlı enerji maliyeti tahmini

- **Korelasyon hipotezi:** Yüksek troposferik NO₂ sütunu (mol/m²), yanma/yüksek sıcaklık süreçleri ile **zayıf veya dolaylı** ilişkili bir proxy olabilir; **yakıt tüketimi veya marj** ile birebir örtüşme garantisi yoktur.
- **Tahmin kullanımı:** “Yüksek NO₂” gözlemi, **maliyet baskısı senaryolarını** tartışmak için **işaretçi** olarak kullanılabilir; nedensellik ve rakip ayrıştırması ayrı analiz gerektirir.

---

## 3. Katmanlı abonelik (SaaS) — alternatif veri ve stratejik fiyatlandırma mimarisi

Aşağıdaki **USD aralıkları yalnızca stratejik referans / örnekleştirmedir**; teklif, vergi, sözleşme ülkesi ve tesise özel kapsam ile değişir. Satış dokümanında mutlaka **feragat**, veri gecikmesi ve uydu sınırları tekrarlanmalıdır.

| Paket (SaaS) | Hedef kitle | İçerik ve özellikler | Önerilen fiyatlama (gösterge) |
|--------------|-------------|----------------------|--------------------------------|
| **ESG Watch (Basic)** | Sürdürülebilirlik analistleri, STK’lar | Aylık mühürlü PDF raporları; temel NO₂ emisyon takibi; kamuya açık / sınırlı dashboard erişimi | **USD 250 – 500 / ay** (tesis başına, gösterge) |
| **Market Alpha (Pro)** | Portföy yöneticileri, emtia tüccarları | Canlı dashboard; **Tahmini Üretim Kapasitesi** gibi finansal proxy’ler (`capacity_proxy`); Excel/CSV veri aktarımı; **kapalı devre** dağıtım (kurumsal IP / SSO+2FA ile barındırma — dağıtım katmanı) | **USD 1.500 – 3.000 / ay** (sektörel paket, gösterge) |
| **Institutional (Enterprise)** | Hedge fonlar, yatırım bankaları | API entegrasyonu; günlük **anomali** alarmları (ör. ani ısı düşüşü); ham uydu katmanları / özel SLA | **USD 10.000+ / yıl** (özel kontrat, gösterge) |

**Önceki iç adlar (eşleme):** Gözlemci (Basic) ≈ **ESG Watch**; Stratejist (Pro) ≈ **Market Alpha**; İstihbarat (Enterprise) ≈ **Institutional**.

**Fiyatı destekleyen “alternatif veri” argümanları (özet):** (i) Kamuya açık fiyat ve üretim istatistiklerinden **önce** veya **paralel** operasyonel sinyal; (ii) Tesis çekirdeğine sabit AOI ile **karşılaştırılabilir** seri; (iii) Metodoloji dosyası ile **izlenebilir** maske ve birim disiplini — bunların tamamı premium katmanlarda **hız + güven** olarak paketlenir.

---

## 4. Fiyat savunması — üç ana değer (müşteri iletişimi)

Aşağıdaki ifadeler **satış ve ürün anlatımı** içindir; gerçek zamanlama, getiri veya düzenleyici sonuç **garanti edilmez**. Her görüşmede **[cco-audit-methodology.md](./cco-audit-methodology.md)** feragatına uygun dil kullanılmalıdır.

### 4.1 Öncü gösterge avantajı (alpha generation — örnek çerçeve)

- **Anlatı:** Uydu tabanlı termal + NO₂ özetleri, resmi finansal tabloların veya üretim duyurularının **yayımlanma döngüsüne göre daha erken veya daha sık** güncellenebilir bir **operasyonel proxy** sunabilir.
- **Örnek (sayısal illüstrasyon):** Akçansa için **19.25 °C** gözlemi üzerinden demo model ile **%83.17** Tahmini Üretim Kapasitesi (`estimate_capacity` / `format_capacity_pct_precise`; iletişimde ≈83.2% kısaltması kullanılabilir) — tek başına üretim tonajı veya gelir tahmini değildir; portföy veya emtia kararlarında **ek bir erken uyarı katmanı** olarak konumlanır.
- **Risk uyarısı:** “Üç ay önce tespit” gibi **kesin gecikme farkı** tesise, rapor tarihine ve veri penceresine bağlıdır; **arbitraj veya getiri vaadi** yapılmamalıdır.

### 4.2 Bağımsız doğrulama (greenwashing protection)

- Şirket içi beyanlara ek olarak, **mühürlü** çıktı ve **açık metodoloji** (Landsat C2 L2, Sentinel-5P L3 referansları) ile izlenebilir maske politikası sunulur.
- Bu, ESG ve reputasyon riskinde **üçüncü taraf uydu kanıtı** ile tartışmayı güçlendirir; düzenleyici “uygunluk” yerine **operasyonel şeffaflık ve iç kontrol** dilinde konumlanır.

### 4.3 Sürekli izleme maliyeti (operasyonel verimlilik)

- Saha denetimi: ulaşım, konaklama, randevu ve tekil örnekleme maliyeti.
- Dijital panel: AOI sabitli **tekrarlanabilir** gözlem, güncellenebilir dashboard/API ve (kurumsal pakette) **7/24 uyarı** mimarisine doğru ölçekleme — birim gözlem başına maliyetin düşürülmesi hedeflenir (kesin TCO karşılaştırması sözleşme kapsamına bağlıdır).

---

## 5. Ek gelir kalemleri (upsell)

Abonelik dışında faturalandırılabilecek **profesyonel hizmet** örnekleri:

| Kalemi | Açıklama |
|--------|-----------|
| **Özel denetim talebi (on-demand)** | Abonelik kapsamı dışındaki koordinatlar (ör. rakip fabrika, enerji santrali) için tek seferlik **Deep Dive** raporu üretimi ve teslim SLA’sı |
| **Tarihsel veri seti (historical data)** | Örneğin son **24 ay** termal ve NO₂ trendlerini içeren ham / işlenmiş veri paketi (lisans ve kullanım sınırları sözleşmede) |
| **Stratejik danışmanlık** | Verilerin **GRC**, iç kontrol ve uyum süreçlerine entegrasyonu için **CCO danışmanlık saatleri** veya çeyrek dönem brifing paketi |

Upsell tekliflerinde de **uydu proxy sınırları** ve **yatırım tavsiyesi olmadığı** açıkça yazılmalıdır.

---

## 6. Sektörel kapalı devre, QOR takvimi ve mühürlü operasyonel endeks

- **Yayın modeli:** Raporlar genel erişime açılmadan, yalnızca **doğrulanmış paydaşlara** (NDA + sözleşme) ve **filigranlı** paketlerle sunulur; teknik detay ve hukuki çerçeve: **[georisk-sealed-index-closed-loop-publishing.md](./georisk-sealed-index-closed-loop-publishing.md)**.  
- **Takvim:** Her çeyrek **Quarterly Operational Review (QOR)** — mühürlü çıktı + metodoloji sürümü + veri penceresi özeti (çimento ve trafo aynı metrik üçgeni: termal / emisyon / aktivite-lojistik bağlamı).  
- **Standart testi:** Karbon uzmanı görüşmesi için kritik soru ve “öz-doğrulama vs resmi kanıt” ayrımı aynı dokümanda sabittir.  
- **Birincil sektör önceliği (SKDM):** [sectors-skdm-primary-priorities.md](./sectors-skdm-primary-priorities.md).  
- **GitHub arşivi ve standartlar:** Çeyrek bazlı dondurma `data/archive/YYYY-Qn/` (ör. `data/archive/2026-Q1/MANIFEST.yml`); sektörel veri kabul dokümanları **[../standards/README.md](../standards/README.md)**. Git operasyonu: **[../standards/github-archive-and-immutability.md](../standards/github-archive-and-immutability.md)**.

---

## İlgili dosyalar

- Birleşik termal + NO₂ metodolojisi: [cco-audit-methodology.md](./cco-audit-methodology.md)  
- Üretim girişleri: `scripts/run_integrated_audit.py`, `scripts/run_audit.py`, `scripts/audit_dashboard.py`  
- Örnek Market Alpha teklif şablonu (Pro): [proposals/teklif-market-alpha-sektorel-hareketlilik-kapasite-2026-05.md](./proposals/teklif-market-alpha-sektorel-hareketlilik-kapasite-2026-05.md)  
- Kamu whitepaper (dashboard sekmesi): [whitepaper-operational-verification-public.md](./whitepaper-operational-verification-public.md) · NDA teknik özet: [due-diligence/README.md](./due-diligence/README.md) · Proprietary ifade: [proprietary-thermal-capacity-proxy.md](./proprietary-thermal-capacity-proxy.md)  
- Mühürlü operasyonel endeks + kapalı devre + QOR: [georisk-sealed-index-closed-loop-publishing.md](./georisk-sealed-index-closed-loop-publishing.md)  
- Birincil sektör öncelikleri (SKDM): [sectors-skdm-primary-priorities.md](./sectors-skdm-primary-priorities.md)  
- Veri kabul standartları (sektörel): [../standards/README.md](../standards/README.md) · Çeyrek arşivi: [../../data/archive/README.md](../../data/archive/README.md)
