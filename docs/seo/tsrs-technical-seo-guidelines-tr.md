# GeoRisk Engine - Technical SEO & Keyword Integration Guidelines

Bu doküman, `/services/tsrs-compliance` sayfasındaki İngilizce içeriklerin Türkiye regülasyon terminolojisiyle (TSRS/KGK) optimize edilmesi sırasında uyulması gereken standartları kapsar.

## 1. Terminoloji ve Akronim Kullanımı

- İlk kullanımda `Turkish Sustainability Reporting Standards (TSRS)` formatı kullanılmalıdır.
- İlk kullanımda `Public Oversight Authority of Turkey (KGK)` formatı kullanılmalıdır.
- TSRS, IFRS S2 ile; KGK, ISSB bağlamıyla ilişkilendirilmelidir.

## 2. Atomic Summary Standartları

- Özetler 40-60 kelime aralığında kalmalıdır; ideal aralık 45-49 kelimedir.
- Yapı: tanım + TSRS/KGK bağlamı + GeoRisk Engine çözümü.
- Subjektif pazarlama cümleleri yerine teknik ve veri odaklı dil kullanılmalıdır.

## 3. JSON-LD @graph Entegrasyonu

- `Organization.knowsAbout`: `TSRS`, `KGK`, `IFRS S2`, `Climate Risk Quantification`.
- `Service.serviceType`: `Climate Risk Reporting for TSRS 2` dahil olmalıdır.
- `FAQPage` soruları doğrudan kullanıcı niyetini yansıtmalıdır, örn. `How to comply with KGK mandates?`.

## 4. Karşılaştırmalı Tablo Hijyeni

Tablo headerları şu sırayla kullanılmalıdır:

| Requirement | Global Reference (IFRS) | Local Mandate (TSRS/KGK) |
| --- | --- | --- |

## 5. Keyword Ownership

- `TSRS Compliance` ve `KGK Audit` yoğunluğu `/services/tsrs-compliance` sayfasında kalmalıdır.
- Blog sayfası reporting/guidance dilini kullanır; satış sayfasına `TSRS Compliance Turkey` anchor text ile iç link verir.

## 6. Teknik Doğrulama

Verifier şu kontrolleri yapar:

1. `robots.txt` ve `sitemap.xml` içinde HTML fallback bulunmamalıdır.
2. Canonical ve URL consistency kontrolleri geçmelidir.
3. Eski redirect URL'leri sitemap içinde yer almamalıdır.
4. TSRS/KGK ilk kullanım formatı ve JSON-LD @graph gereklilikleri doğrulanmalıdır.
