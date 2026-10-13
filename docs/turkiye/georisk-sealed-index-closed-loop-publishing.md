# GeoRisk — mühürlü operasyonel endeks: kapalı devre yayın ve standart testi

Bu not, **ürün / GRC / satış** iletişimi için kurumsal çerçeveyi sabitler. **Hukuki tavsiye değildir**; IP filigranı, NDA ve veri sızıntısı için **bağımsız hukuk danışmanı** ile sözleşme metni üretilmelidir.

---

## 1. Sektörel kapalı devre yayın modeli

**Amaç:** Raporları genel internete açmak yerine, yalnızca **doğrulanmış (verified)** paydaşlara sunarak verinin **ticari istihbarat** niteliğini korumak.

### 1.1 Whitelist erişimi (Market Alpha ve üzeri)

- **Kurumsal IP allowlist** ve/veya **kurumsal SSO + 2FA** (ör. SAML/OIDC sağlayıcısı) ile dashboard erişimi **abonelik sözleşmesine** bağlanmalıdır.  
- **Uygulama:** Streamlit tek başına güçlü bir edge firewall değildir; üretimde tipik desen **ters vekil (nginx / Envoy)**, **Cloudflare Zero Trust / IAP**, veya **VPN** arkasında barındırmaktır.  
- **Konfigürasyon ipucu:** Dağıtım ortamında ortam değişkeni ile alıcı etiketi taşınır (`GEORISK_REPORT_WATERMARK`, bkz. `.env.example`).

### 1.2 Filigranlı (watermarked) raporlar

- Her indirilen PDF/Markdown paketinde **alıcı kurum + sözleşme dönemi** (ve mümkünse **indirme olayı kimliği**) metinsel filigran olarak yer almalıdır.  
- **Hukuki amaç:** Sızıntı halinde **iz sürmek ve sözleşme ihlali** iddiasını desteklemek; filigran **tek başına sızıntıyı “fiziksel olarak engellemez”**.  
- **Teknik yol haritası:** PDF için şeffaf metin katmanı / görünür footer; görüntü tabanlı filigran için ayrı render hattı. Bu repo OSS hattında **metinsel filigran** (`GEORISK_REPORT_WATERMARK`) ile başlar.

### 1.3 Periyodik yayın takvimi — Quarterly Operational Review (QOR)

- **Standart:** Her takvim çeyreği sonunda **Quarterly Operational Review (QOR)** paketi: mühürlü rapor + metodoloji sürümü + veri penceresi özeti.  
- **Karşılaştırılabilirlik:** Aynı metrik seti (aşağıda) ve sabit AOI politikası ile **geçmişe göre sapma** analizleri mümkün olur.  
- **GitHub arşivi:** Çeyrek dondurması `data/archive/YYYY-Qn/` altında **MANIFEST** ile sabitlenir; sektörel veri kabul standartları `docs/standards/` altında sürümlenir. Operasyon: [github-archive-and-immutability.md](../standards/github-archive-and-immutability.md).

---

## 2. GeoRisk mühürlü operasyonel endeks — veri seti donanımı ve değişmezlik

**Özet:** Endeksin “standart” sayılması için metodoloji ve ürün hattının **sürümlenmiş değişmezliği** (immutable snapshots: metin + kod + mühür) şarttır; bu, **Git mührü** ve **yayınlanmış metodoloji dosyası** ile başlar; kurumsal olarak **imzalı artefact** (release) ile güçlendirilir.

### 2.1 Çok sektörlü aynı metrik üçgeni

| Sütun | Çimento | Trafo |
| --- | --- | --- |
| **Termal** | Birincil kanıt (fırın proxy) | Çatı / geniş AOI bağlamı (ikincil) |
| **Emisyon** | NO₂ (L3) | NO₂ + CO (L3) |
| **Lojistik / aktivite** | NO₂ bağlamı + (kurumsal) lojistik genişletme | VIIRS DNB + (kurumsal) lojistik proxy |

Genişleyen birincil sektör öncelikleri: **[sectors-skdm-primary-priorities.md](./sectors-skdm-primary-priorities.md)**.

### 2.2 Altın standart sertifikasyon ibaresi (rapor dili)

Raporlarda aşağıdaki ibare **teknik referans** iddiası taşır; **düzenleyici onay veya resmi sertifika** değildir:

> **Bu veri özeti, Landsat Collection 2 Level-2 (QA_PIXEL maskeli termal üretim hattı) ve Sentinel-5P OFFL L3 troposferik ürün çizgisi protokolleriyle üretim hattında mühürlenmiştir.** Trafo hattında ayrıca VIIRS DNB aylık bileşikleri raporlanır.

Kısa varyant trafo mühürlü rapor şablonunda **Altın Protokol Mührü** başlığı altında yer alır.

### 2.3 Şeffaf hata payı — `cf_cvg` ve bulutluluk dili

- VIIRS `avg_rad` yorumu, **bulut örtüsü ve gözlem sayısı** nedeniyle belirsiz taşır. Ürün bandı **`cf_cvg`** (cloud-free coverage count) AOI ortalaması olarak rapora yazılmalıdır; düşük `cf_cvg` **“gece ışığı düşük = kapalı”** anlamına gelmez.  
- Landsat tarafında **QA_PIXEL** ile bulut/gölge politikası raporda referanslanır (`cco-audit-methodology.md`).

---

## 3. Karbon ayak izi uzmanı ile “standart testi” (görüşme sorusu)

Aşağıdaki soru, ürünün **bağımsız kanıt** vaadini ölçülü şekilde kalibre eder:

> “Bu veri seti, yıllık karbon beyanımda **bağımsız üçüncü taraf kanıtı** olarak sunabileceğim **resmi bir formata** sahip mi — yoksa **denetim öncesi öz-doğrulama ve çapraz soru** için mi konumlanmalı?”

- **Evet** denmesi beklenen doğru çerçeve çoğu kurumda: **Öz-doğrulama + denetim hazırlığı** (kapalı devre mühürlü paket, metodoloji, filigran, QOR).  
- **Resmi “tek başına düzenleyici kanıt”** iddiası genelde **hayır** olmalıdır; aksi iddia **hukuki ve itibar riski** taşır.

Bu çerçeve kabul edilirse, kapalı devre raporlar sektörde **“Denetim öncesi öz-doğrulama”** pratiği için **referans paket** haline gelebilir.

---

## İlgili dosyalar

- Abonelik ve altın standart tablo: [golden-standard-subscription-and-analytics.md](./golden-standard-subscription-and-analytics.md)  
- Birincil sektör öncelikleri (SKDM): [sectors-skdm-primary-priorities.md](./sectors-skdm-primary-priorities.md)  
- Birleşik metodoloji: [cco-audit-methodology.md](./cco-audit-methodology.md)  
- Kamu whitepaper: [whitepaper-operational-verification-public.md](./whitepaper-operational-verification-public.md)  
- Trafo Primary Audit: [transformers/README.md](./transformers/README.md)  
- Sektörel veri kabul standartları: [../standards/README.md](../standards/README.md)  
- Çeyrek arşivi: [../../data/archive/README.md](../../data/archive/README.md)  
- Buluş bildirimi / FM stratejisi (iç, patent vekili öncesi): [ip-bulus-bildirimi-ve-fikri-mulkiyet-stratejisi-tr.md](./ip-bulus-bildirimi-ve-fikri-mulkiyet-stratejisi-tr.md)
