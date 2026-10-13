# Keyword cannibalization audit

Bu kontrol, indekslenebilir statik sayfaların hedef sorgu niyetini ayrıştırmak için yapıldı. Amaç, aynı ana keyword için birden fazla sayfanın rekabet etmesini önlemek ve topic-cluster sayfalarını fan-out alt sorgulara net şekilde atamaktır.

## Canonical intent map

| URL | Primary intent | Sahiplenmesi gereken keyword | Destekleyici / ikincil keyword |
| --- | --- | --- | --- |
| `/hizmetler` | Ana Geospatial Hub | `Konum Zekası`, `Risk Puanlama`, `Uydu Verisi`, `Geospatial Risk Intelligence Platformu` | operasyon ekipleri, mühendisler, sigortacılar |
| `/services` | Main services and Geospatial Intelligence | `geospatial intelligence services`, `industrial risk analytics`, `satellite-based indicators` | enterprise risk teams, operations, insurance, engineering |
| `/services/tsrs-compliance` | Turkey-focused English service landing | `TSRS Compliance Turkey`, `Sustainability reporting standards in Turkey (TSRS)` | TSRS 1, TSRS 2, reporting evidence, FAQPage |
| `/konum-zekasi-platformu` | Platform seçim kriterleri | `konum zekası platformu` | API, raporlama, uydu göstergesi |
| `/lokasyon-risk-analizi-araclari` | Araç kabiliyeti ve ölçülen sinyaller | `lokasyon risk analizi araçları` | flood, heat, wildfire, industrial context |
| `/georisk-engine-ozellikleri` | Ürün özellikleri | `GeoRisk Engine özellikleri` | API, PDF rapor, audit workflow |
| `/iklim-riski-fiyatlandirma` | Satın alma / fiyatlandırma kapsamı | `iklim riski analitiği fiyatlandırması` | tesis sayısı, veri derinliği, rapor sıklığı |
| `/konum-zekasi-cevresel-risk-yonetimi` | Çevresel risk yönetimi rehberi | `çevresel risk yönetimi`, `deprem sel iklim değişikliği riskleri` | konum zekası, jeopati, mikrobölgeleme, hidrolojik modelleme |

## Findings

1. `/hizmetler` ana sayfası bilinçli olarak broad authority page rolünde kalır. Primary geospatial / TSRS / sector keyword kümeleri burada tutulur.
2. `/georisk-engine-ozellikleri` ilk taslakta `geospatial risk intelligence`, `climate risk analytics` ve `industrial risk scoring` ifadelerini fazla sahipleniyordu. Bu, `/hizmetler` ile cannibalization riski yaratıyordu.
3. `/konum-zekasi-platformu` ve `/lokasyon-risk-analizi-araclari` sayfalarında bazı İngilizce primary keyword ifadeleri destekleyici bağlamda geçiyordu; exact-match yoğunluk azaltıldı.
4. Topic-cluster sayfaları sitemap ve Vercel rewrite ile ayrı URL olarak yayınlanır, ancak canonical intentleri farklıdır.

## Applied fixes

- `/georisk-engine-ozellikleri` title/description ve gövde metni API, PDF report, audit workflow ve ürün kabiliyetlerine daraltıldı.
- `/konum-zekasi-platformu` sayfasındaki generic primary keyword cümlesi Türkçe platform seçim bağlamına çevrildi.
- `/lokasyon-risk-analizi-araclari` sayfasındaki sector exact-match ifadeleri araç kabiliyeti bağlamına indirildi.
- `/hizmetler` içindeki topic-cluster tablosu internal navigation olarak bırakıldı; ana sayfanın broad authority rolü korunur.

## Ongoing rule

Yeni sayfa eklenirken önce `Canonical intent map` güncellenmeli. Aynı exact-match keyword title, H1 ve meta description içinde birden fazla sayfada primary intent olarak kullanılmamalıdır.


## Final kontrol sonucu

Son matris kontrolünde `count >= 2` eşiğinde birden fazla sayfada primary overlap kalmadı. Kalan tekil geçişler internal navigation veya topic-cluster bağlamı olarak kabul edilir.

| Keyword | Primary owner | Not |
| --- | --- | --- |
| `geospatial risk intelligence` | `/hizmetler` | Hub / ana hizmet sayfası |
| `konum zekası platformu` | `/konum-zekasi-platformu` | Platform seçim alt sorgusu |
| `lokasyon risk analizi` | `/lokasyon-risk-analizi-araclari` | Araç kabiliyeti alt sorgusu |
| `GeoRisk Engine özellikleri` | `/georisk-engine-ozellikleri` | Ürün özellikleri alt sorgusu |
| `iklim riski analitiği fiyatlandırması` | `/iklim-riski-fiyatlandirma` | Satın alma / fiyatlandırma alt sorgusu |
| `Audit-Ready` | `/services` | Regülatif services sayfasına rezerve edildi; `/hizmetler` methodologically transparent / scientifically validated / peer-reviewed data protocols dilini kullanır |

Kontrol kuralı: Aynı exact-match keyword birden fazla sayfada title/H1/meta description düzeyinde primary intent olarak kullanılmamalıdır. Internal link veya topic-cluster tablosunda tekil geçiş kabul edilebilir.

- `/konum-zekasi-cevresel-risk-yonetimi` sayfası, `/konum-zekasi-platformu` ile aynı platform seçim intentini hedeflemez; çevresel risk yönetimi ve deprem/sel/iklim değişikliği açıklayıcı rehber intentini hedefler.

- `/services` İngilizce hizmet ana sayfasıdır; `/hizmetler` ise Türkçe / Türkiye odaklı hizmet hub rolünü korur. hreflang/canonical ayrımıyla dil intentleri ayrıştırılır.

- `/services/tsrs-compliance` owns the English informational blog intent for TSRS standards; `/services` owns the commercial services / TSRS Compliance Turkey service intent.


## Services vs Hizmetler intent split

| Page | Role | H1 | Keyword cluster | Target audience |
| --- | --- | --- | --- | --- |
| `/services` | Global / regulatory focus | `Industrial Climate Risk & Compliance Services` | `IFRS S2`, `TSRS Compliance`, `Audit-Ready`, `ESG` | Auditors, ESG offices, global investors |
| `/hizmetler` | Main Geospatial Hub | `Geospatial Risk Intelligence Platformu` | `Konum Zekası`, `Risk Puanlama`, `Uydu Verisi` | Operasyon ekipleri, mühendisler, sigortacılar |

Bu ayrım gereği `/services` regülasyon ve compliance dilini, `/hizmetler` ise operasyonel geospatial platform dilini sahiplenir.


## TSRS blog canonical split

`/blog/tsrs-compliance-guide` is the canonical educational BlogPosting for TSRS definitions, KGK context and reporting explanations; it avoids the commercial `TSRS Compliance Turkey` service phrase except where linking context requires it. `/services/tsrs-compliance` is a shorter service landing page that links to the blog and does not duplicate BlogPosting content.


## Minimal sitemap policy

`sitemap.xml` intentionally lists the homepage, `/services`, and `/services/tsrs-compliance` as the primary authority hierarchy. Supporting pages (`/hizmetler`, `/blog/tsrs-compliance-guide` and topic-cluster URLs) remain static, internally linked and rewrite-enabled, but are not included in the submitted sitemap to keep crawl priority focused.


## `/hizmetler` audit-ready reservation

`Audit-Ready` and `audit-ready` exact phrases are reserved for `/services`. `/hizmetler` must use `methodologically transparent`, `scientifically validated`, and `peer-reviewed data protocols` for operational/geospatial validation language.


## TSRS blog reporting language

The canonical blog `/blog/tsrs-compliance-guide` avoids commercial `TSRS Compliance` language. It uses `TSRS Reporting Framework`, `Aligning with TSRS Standards`, and `TSRS Disclosure Requirements` to preserve educational / guidance intent.


## Sitemap authority hierarchy

Submitted sitemap priority is used to express authority hierarchy:

| URL | Priority | Role |
| --- | --- | --- |
| `/` | `1.0` | Brand / homepage root |
| `/services` | `0.9` | Main services and geospatial intelligence page |
| `/services/tsrs-compliance` | `0.8` | TSRS Compliance Turkey service landing |

Other supporting static pages remain available through internal links and Vercel rewrites, but are not submitted in sitemap.
