# Buluş bildirimi taslağı ve fikri mülkiyet stratejisi (iç — patent vekili öncesi)

**Sınıflandırma:** İç · GeoRisk Engine  
**Not legal advice:** Bu metin **patent başvurusu, öncelik hakkı veya buluş kabulü yerine geçmez**. Bağımsız **patent vekili** ve kurum hukuku ile **buluş bildirim formu (Invention Disclosure)** resmileştirilmelidir. Kamuya açık beyanlarla çelişen ifadeler (ör. sabit korelasyon oranı) **vekâlet görüşmesinde dahi** dikkatle kullanılmalıdır.

---

## 1. Buluş bildirimi — teknik özet (taslak)

### 1.1 Teknik problem

Endüstriyel tesislerde (ör. çimento, trafo, demir-çelik vb.) **operasyonel yoğunluk** ve **karbon / enerji beyanları**, tesis dışından ve bağımsız bir gözlemle **düşük gecikmeyle**, **tekrarlanabilir** ve **denetlenebilir** biçimde doğrulanmakta zorlanır. Klasik çözümler ya sahaya erişim gerektirir ya da tek spektral kanal / tek göstergede kalır; **OSB içi komşu tesis gürültüsü** ve **meteorolojik karışım** altında kaynak ayrımı zayıftır.

### 1.2 Teknik çözüm (sistem + yöntem unsurları)

Çok spektral uydu verilerinin birlikte işlenmesi:

- **Termal:** Landsat Collection 2 Level-2, **QA_PIXEL** maskeli bileşik üzerinden yüzey sıcaklığı proxy’si.  
- **Emisyon:** Sentinel-5P **OFFL L3** troposferik NO₂ (ve trafo hattında CO) sütun ortalamaları.  
- **Aktivite:** VIIRS DNB aylık bileşik (`avg_rad`) ve raporda **`cf_cvg`** ile şeffaf kalite bağlamı.  
- **Arka plan normalizasyonu (Halka / Ring):** Tesis AOI’si \(S\) için \(R\) metre tamponlu halka \(B = \text{buffer}(S, R) \setminus S\) üzerinde aynı ürünlerin ortalaması alınarak **AOI − ring** **residual** üretimi; bu, “komşu sanayi gürültüsü”ne karşı **bilgisayar destekli normalizasyon katmanı**dır (kaynak ayırımı garantisi değildir).  
- **Sektöre özel hibrit metodoloji:** Çimento için termal ağırlıklı; trafo için emisyon + gece ışığı ağırlıklı **aynı metrik üçgeni** disiplini ([sectors-skdm-primary-priorities.md](./sectors-skdm-primary-priorities.md), [georisk-sealed-index-closed-loop-publishing.md](./georisk-sealed-index-closed-loop-publishing.md)).  
- **Kapasite ve operasyonel proxy:** Referans dönemlerine göre **yüzde veya skor ölçekli** gösterge; **asıl sayısal dönüşüm katsayıları ve eşikler** ticari sır olarak ayrı tutulur ([proprietary-thermal-capacity-proxy.md](./proprietary-thermal-capacity-proxy.md), [proprietary-transformer-logistics-capacity-proxy.md](./proprietary-transformer-logistics-capacity-proxy.md)).

### 1.3 Yenilik (novelty) — vekille tartışılacak çerçeve

- Yalnızca optik görüntüleme değil; **termal imza + gaz sütunu + gece ışığı** sinyallerinin **yapılandırılmış çapraz okunması** ve **halka tabanlı arka plan çıkarma** ile OSB ortamında **operasyonel denetim** hedeflenmesi.  
- **Sektör modu** (çimento vs. trafo) ile aynı üretim hattında **farklı fizik varsayımlarına** uyum.  
- **Mühürlü rapor + Git commit özeti + çeyrek arşiv manifesti** ile **izlenebilir üretim** (bkz. [data/archive/README.md](../../data/archive/README.md)).

**Kamusal tutarlılık uyarısı:** Whitepaper ve kamu metinlerinde **sabit “%90+ korelasyon”** gibi iddialar **bilinçli olarak kullanılmaz**; vekâlette de kamuya sızmayacak şekilde **tesise özel doğrulama** diline hizalanmalıdır ([whitepaper-operational-verification-public.md](./whitepaper-operational-verification-public.md)).

---

## 2. Kademeli savunma (patent vekili gündemi)

Üç katman **birbirini tamamlar**; içerik ifşası ve patent kapsamı için vekâlet stratejisi şarttır.

| Katman | Korunan unsur | Not |
| --- | --- | --- |
| **Sistem (apparatus / system)** | Veri çekme, AOI yönetimi, halka geometrisi, ürün seçimi, rapor üretimi, mühür ve arşiv manifesti ile **uçtan uca denetim üretim hattı** | Yazılım mimarisi + iş akışı; açık kaynak bileşenlerin (EE, açık veri) **kombinasyonu** ve **teknik etki** tartışılır |
| **Yöntem (method)** | Ham spektral zaman serilerinin **normalizasyonu**, residual üretimi, çok kanallı birleştirme **çerçevesi** (algoritma iskeleti) | **Kamuya açılmayan** matematiksel ayrıntı vektörü; katsayıların bir kısmı ticari sırda kalabilir |
| **Ticari sır (trade secret)** | Regresyon / ağırlıklandırma katsayıları, müşteriye özel eşikler, kalibrasyon paketleri | [proprietary-*.md](./proprietary-thermal-capacity-proxy.md) ile sınıflandırılır; patent metninde **ne kadarının** açıklanacağı vekille belirlenir |

**Yöntem patenti ifadesi (düzeltilmiş):** “Ham spektral veriyi **sabit %90+ korelasyonlu** üretim kapasitesine çeviren yöntem” ifadesi **kamu dokümanlarımızla çelişir** ve savunma riski yaratır. Vekâlete önerilen formülasyon: “**Kalibre edilmiş operasyonel kapasite proxy’sine** dönüşüm; korelasyon iddiası **tesis bazlı doğrulama** ve sözleşme kapsamına bağlıdır.”

---

## 3. Fikri mülkiyet envanteri ve Git mührü (dijital zaman damgası)

### 3.1 Metodoloji sürüm etiketleri (iletişim / envanter)

| Hat | Repo referansı | Sürüm etiketi (iç) |
| --- | --- | --- |
| Çimento — termal tabanlı operasyonel doğrulama | [cco-audit-methodology.md](./cco-audit-methodology.md) + üretim betikleri | **v1.0** |
| Trafo — emisyon + lojistik ESG doğrulaması | [transformers/transformer-audit-methodology.md](./transformers/transformer-audit-methodology.md) + `scripts/transformer_audit.py` | **v1.2** |

Sürüm numaraları **repo içi iletişim etiketidir**; patent başvuru numarası veya hukuki sürüm değildir. İleride `CHANGELOG` veya tag politikası ile hizalanmalıdır.

### 3.2 `git rev-parse HEAD` ve arşiv

- Mühürlü raporlarda görünen **Git commit özeti**, **iç süreç mühürü** ve **ürün çıktısının hangi kod/metin durumuyla** üretildiğini eşler.  
- **Öncelik hakkı (priority) / icat tarihi** tek başına bu mühürle **ispatlanmış sayılmaz**; ülkeye göre **ilk başvuru**, **geçici (provisional) başvuru**, **noter / zaman damgalı** kanıt zinciri vekâille değerlendirilir.  
- Çeyrek arşivi: `data/archive/YYYY-Qn/MANIFEST.yml` — metodoloji ve standart dosya yollarının **o çeyreğe ait anlık görüntüsü**.

### 3.3 GRC dokümantasyon mülkiyeti

Proprietary metinlerde belirtildiği üzere metodoloji dokümantasyon bakımı **GRC yönetişimi** altında izlenir; bu, **kurumsal mülkiyet ve süreç sorumluluğu** kaydıdır; **“o tarihte icat edilmiştir”** anlamında **otomatik hukuki delil** oluşturmaz.

---

## İlgili dosyalar

- Kapalı devre ve mühürlü operasyonel endeks: [georisk-sealed-index-closed-loop-publishing.md](./georisk-sealed-index-closed-loop-publishing.md)  
- Git arşiv operasyonu: [../standards/github-archive-and-immutability.md](../standards/github-archive-and-immutability.md)  
- Ticari sır — termal: [proprietary-thermal-capacity-proxy.md](./proprietary-thermal-capacity-proxy.md)  
- Ticari sır — trafo: [proprietary-transformer-logistics-capacity-proxy.md](./proprietary-transformer-logistics-capacity-proxy.md)
