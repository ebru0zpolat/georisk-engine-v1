# Google indeks kapsamı

Ürün sayfasından önce yanıtlanacak temel soru: **Google neyi indeksleyecek?**

Bu dalda hedef indeks yüzeyi aşağıdaki gibi tanımlıdır:

| URL | İndeks niyeti | Canonical | İçerik tipi |
| --- | --- | --- | --- |
| `https://georiskengine.com/` | Ana marka ve platform konumlandırması | `https://georiskengine.com/` | Statik HTML ana sayfa |
| `https://georiskengine.com/hizmetler` | Hizmet kapsamı: iklim, endüstriyel ve jeo-uzamsal risk zekası | `https://georiskengine.com/hizmetler` | Statik, taranabilir HTML hizmet sayfası |
| `https://georiskengine.com/sitemap.xml` | Arama motorlarına keşif listesi | Kendisi | XML sitemap |
| `https://georiskengine.com/robots.txt` | Tarama izni ve sitemap yönlendirmesi | Kendisi | Robots metni |

## Uygulama notları

- `/hizmetler` sayfası JavaScript çalışmasını beklemeden ilk HTML yanıtında başlık, açıklama, H1, hizmet kartları ve yapılandırılmış veri içerir.
- SPA fallback'i Cloudflare Pages kendisi sağlar (`dist/404.html` olmadığı sürece eşleşmeyen yollar `index.html` döner; `_redirects` içinde catch-all satırı yoktur). Buna rağmen indekslenmesi hedeflenen sayfalar kendi statik HTML çıktısına sahip olmalıdır.
- Sayfa başlıkları ve meta açıklamalar, kullanıcı arama niyetini açıkça karşılamalıdır; yalnızca marka adı veya kısa ürün sloganı yeterli değildir.
- Uydu tabanlı çıktılar operasyonel karar desteği olarak konumlandırılır; düzenleyici kesin kanıt veya yatırım tavsiyesi gibi sunulmaz.


## Primary keyword map

| Primary keyword | Hedef URL | Sayfadaki rol |
| --- | --- | --- |
| `geospatial risk intelligence` | `/`, `/hizmetler` | Ana kategori ve H1 / hero bağlamı |
| `climate risk analytics` | `/`, `/hizmetler` | Platform açıklaması ve hizmet kartı |
| `industrial risk scoring` | `/`, `/hizmetler` | Sanayi tesisi skorlama hizmeti |
| `satellite-based risk assessment` | `/`, `/hizmetler` | Uydu göstergeleriyle risk değerlendirme kapsamı |
| `enterprise climate risk platform` | `/`, `/hizmetler` | Kurumsal platform konumlandırması |

Bu kelimeler title, description, H1/H2 ve gövde metnine doğal bağlamla yerleştirilir; aynı ifadelerin gereksiz tekrarından kaçınılır.


## Turkey / TSRS focused keyword map

| Turkey / TSRS keyword | Hedef URL | Sayfadaki rol |
| --- | --- | --- |
| `TSRS climate risk reporting` | `/hizmetler` | Title, description ve Türkiye / TSRS bölümü |
| `TSRS risk analytics` | `/hizmetler` | Türkiye / TSRS hizmet kartı ve OG açıklaması |
| `Türkiye sustainability reporting risk data` | `/hizmetler` | Meta description ve Türkiye sürdürülebilirlik raporlama kartı |
| `industrial climate exposure Türkiye` | `/hizmetler` | Türkiye sanayi tesisi maruziyet notu |

Bu küme Türkiye odaklı arama niyetini karşılar; sayfa, TSRS raporlama ekiplerine veri yüzeyini anlatır ancak düzenleyici kesin kanıt veya hukuki uyum garantisi iddiasında bulunmaz.


## Sector keyword map

| Sector keyword | Hedef URL | Sayfadaki rol |
| --- | --- | --- |
| `steel plant climate risk` | `/hizmetler` | Ağır sanayi / çelik tesisleri kullanım kartı |
| `industrial facility geospatial risk` | `/hizmetler` | Endüstriyel tesis risk kapsamı |
| `port climate risk assessment` | `/hizmetler` | Liman varlıkları iklim riski kullanım kartı |
| `energy infrastructure risk analytics` | `/hizmetler` | Enerji altyapısı risk analitiği kapsamı |
| `factory flood heat wildfire exposure` | `/hizmetler` | Fabrika taşkın, sıcaklık ve yangın maruziyeti kapsamı |

Sektör ifadeleri `/hizmetler` sayfasında kullanım alanı olarak ele alınır; ana sayfa daha geniş platform ve kategori niyetine odaklanır.


## `/hizmetler` heading blueprint

| Tag | Exact heading |
| --- | --- |
| H1 | `Geospatial Risk Intelligence for Industrial Assets` |
| H2 | `What is climate, environmental and location-based risk scoring?` |
| H2 | `Who uses geospatial risk intelligence for industrial sites and enterprise risk teams?` |
| H2 | `How do satellite-based indicators support methodologically transparent validation?` |
| H2 | `What are the use cases for steel, energy, ports, manufacturing and real estate?` |
| H2 | `What methodology, data sources and limitations apply?` |


## Atomic answers yöntemi

`/hizmetler` sayfasında her ana bölüm, H2 başlığından hemen sonra 40-60 kelimelik doğrudan bir tanım paragrafı içerir. Bu paragraflar "bu bölümde anlatacağız" gibi giriş cümleleri kullanmaz; konuyu, kullanıcı niyetini, veri kapsamını ve sınırlılığı doğrudan açıklar.

Soru odaklı başlıklar, yapay zeka modellerinin kullanıcı sorularına kısa cevap çekebilmesi için tercih edilir. H2 başlıkları ana soruyu, H3 başlıkları alt niyetleri karşılar.


## Scannability ve yapılandırılmış veri

`/hizmetler` sayfası kritik içeriği JavaScript beklemeden statik HTML içinde sunar. AI botlarının extraction yapabilmesi için hizmet kapsamı, Türkiye / TSRS eşlemesi, sektör kullanım alanları, metodoloji ve FAQ içerikleri karşılaştırmalı tablolarla verilir.

JSON-LD kapsamı:

| Schema type | Amaç |
| --- | --- |
| `Organization` | GeoRisk Engine marka ve sağlayıcı bilgisini tanımlar |
| `Service` | Hizmet kapsamını ve hedef serviceType keyword kümelerini açıklar |
| `Dataset` | Risk göstergeleri veri yüzeyini ve kapsamını tanımlar |
| `FAQPage` | Soru-cevap biçimindeki doğrudan yanıtları makine okunabilir hale getirir |

`_redirects` yalnızca kalıcı yönlendirmeleri taşır (ör. `/sustainability-reporting-standards-turkey-tsrs` → `/services/tsrs-compliance`, 301). `npm run build` sonunda `scripts/flatten-clean-urls.mjs`, canonical'ı `/` ile bitmeyen sayfaları `dist/<sayfa>.html` olarak düzleştirir (ör. `hizmetler.html`); böylece Cloudflare Pages `/hizmetler` adresini sondaki `/` yönlendirmesi olmadan sunar ve Vercel `cleanUrls` aynı URL'leri korur. Fiziksel `robots.txt` ve `sitemap.xml` `frontend/dist` kökünden servis edilir.


## E-E-A-T ve information gain

`/hizmetler` sayfası, özgün bilgi kazanımı için `Türkiye Industrial Climate Exposure 2026` mini case-study tablosunu içerir. Bu tablo çelik, liman, enerji altyapısı ve üretim tesisi arketiplerini özgün risk sinyali ve raporlama değeriyle eşler.

Yazar / reviewer kuralı:

- Public sayfada `GeoRisk Engine Research Team` author ve reviewer entity olarak kullanılır.
- JSON-LD `Service`, `Dataset` ve `CreativeWork` node'ları bu kurumsal author bilgisine bağlanır.
- LinkedIn `sameAs` yalnızca doğrulanmış GeoRisk Engine veya named-author LinkedIn URL sağlandığında eklenmelidir.
- Bu oturumda web araması doğrulanabilir GeoRisk Engine LinkedIn profili bulmadığı için sahte LinkedIn `sameAs` eklenmemiştir.


## Fan-out topic cluster

AI sistemleri tek bir kullanıcı sorusunu alt sorgulara bölebilir. Bu nedenle `/hizmetler` sayfası aşağıdaki statik topic-cluster sayfalarına bağlanır:

| Fan-out sub-query | Static URL | Amaç |
| --- | --- | --- |
| En iyi konum zekası platformu hangisi? | `/konum-zekasi-platformu` | Platform seçim kriterleri |
| Lokasyon risk analizi araçları ne ölçer? | `/lokasyon-risk-analizi-araclari` | Araç kabiliyetleri ve ölçülen risk sinyalleri |
| GeoRisk Engine özellikleri nelerdir? | `/georisk-engine-ozellikleri` | Ürün özellikleri ve farklılaştırıcılar |
| İklim riski analitiği fiyatlandırması nasıl değerlendirilir? | `/iklim-riski-fiyatlandirma` | Fiyatlandırma faktörleri ve satın alma kapsamı |
| Konum zekası ile çevresel risk yönetimi nasıl yapılır? | `/konum-zekasi-cevresel-risk-yonetimi` | Deprem, sel, iklim değişikliği ve ESG risk yönetimi |

Her sayfa `frontend/public/<slug>/index.html` olarak statik HTML üretir ve Vercel clean URL rewrite ile `/<slug>` adresinde yayınlanır; minimal sitemap yalnızca homepage, `/services` ve `/services/tsrs-compliance` URL’lerini listeler.


## Final pre-commit QA checks

- TSRS terminolojisi sayfa içinde TSRS 1 genel sürdürülebilirlik açıklamaları ve TSRS 2 iklimle ilgili açıklamalar ayrımıyla desteklenir.
- Soru formundaki destek sayfaları sitemap içinde `priority 0.80` ile listelenir; homepage `1.00` kalır.
- Yeni görsel `/konum-zekasi-cevresel-risk-yonetimi` sayfasındadır ve alt metin soru-cevap akışını destekler. `/hizmetler` sayfasında yeni görsel bulunmaz.


## English `/services` page

The English `/services` page is the main services and geospatial intelligence page. The Turkey-focused English reporting URL is `/services/tsrs-compliance`, which covers TSRS 1, TSRS 2 and TSRS Compliance Turkey without claiming legal certification or regulatory assurance.

English FAQ summaries are included in `FAQPage` JSON-LD so AI systems can extract service answers without waiting for JavaScript.


## TSRS English blog support

`/services/tsrs-compliance` targets English searches for `Sustainability reporting standards in Turkey (TSRS)`. It explains TSRS 1 and TSRS 2, includes BlogPosting and FAQPage JSON-LD, links to `/services`, and supports `TSRS Compliance Turkey` without claiming legal certification or regulatory assurance.


## Services / Hizmetler split

`/services` global ve regülatif odaklıdır: H1 `Industrial Climate Risk & Compliance Services`, keyword kümesi `IFRS S2`, `TSRS Compliance`, `Audit-Ready`, `ESG`, hedef kitle denetçiler, ESG ofisleri ve global yatırımcılardır.

`/hizmetler` ana geospatial hub olarak konumlanır: H1 `Geospatial Risk Intelligence Platformu`, keyword kümesi `Konum Zekası`, `Risk Puanlama`, `Uydu Verisi`, hedef kitle operasyon ekipleri, mühendisler ve sigortacılardır.


## English TSRS local acronym targeting

`/services/tsrs-compliance` includes `TSRS (Turkish Sustainability Reporting Standards)` and `KGK (Public Oversight Authority of Turkey)` in visible copy, metadata-adjacent content and JSON-LD. This targets Turkish professionals who prefer English search results, including auditors, ESG managers and global investors reviewing Turkey exposure.


## TSRS blog canonical split

`/blog/tsrs-compliance-guide` is the canonical educational BlogPosting for TSRS definitions, KGK context and reporting explanations; it avoids the commercial `TSRS Compliance Turkey` service phrase except where linking context requires it. `/services/tsrs-compliance` is a shorter service landing page that links to the blog and does not duplicate BlogPosting content.


## Minimal sitemap policy

`sitemap.xml` intentionally lists the homepage, `/services`, and `/services/tsrs-compliance` as the primary authority hierarchy. Supporting pages (`/hizmetler`, `/blog/tsrs-compliance-guide` and topic-cluster URLs) remain static, internally linked and rewrite-enabled, but are not included in the submitted sitemap to keep crawl priority focused.


## `/hizmetler` audit-ready alternatives

`Audit-Ready` is reserved for `/services`. The Turkish geospatial hub `/hizmetler` uses more technical and operational alternatives: `methodologically transparent`, `scientifically validated`, and `peer-reviewed data protocols`.


## Sitemap authority hierarchy

Submitted sitemap priority is used to express authority hierarchy:

| URL | Priority | Role |
| --- | --- | --- |
| `/` | `1.0` | Brand / homepage root |
| `/services` | `0.9` | Main services and geospatial intelligence page |
| `/services/tsrs-compliance` | `0.8` | TSRS Compliance Turkey service landing |

Other supporting static pages remain available through internal links and Vercel rewrites, but are not submitted in sitemap.


## Reference frameworks / data sources

`/services` and `/hizmetler` include a visible reference-framework answer for "Who validated the methodology?". The language uses IPCC Scenarios, ESA / Copernicus, and peer-reviewed data protocols as public scientific references. It explicitly avoids claiming endorsement, certification, or partnership unless such proof exists.


## TSRS 2 sample deliverable visual

`/services/tsrs-compliance` includes a static SVG mockup of a TSRS 2 physical climate risk report page. The image shows the expected service output: facility exposure score, evidence table, satellite indicators and methodology notes. The alt text describes the question-answer intent and avoids implying legal assurance or KGK certification.


## One-minute risk scorecard

`/services` includes a lightweight client-side micro-tool titled `Get a 1-Minute Risk Scorecard`. It accepts one coordinate or address and returns an indicative 1-100 Climate Risk Score as a preview flow. The page states that the score is not a certified report or regulatory opinion.
