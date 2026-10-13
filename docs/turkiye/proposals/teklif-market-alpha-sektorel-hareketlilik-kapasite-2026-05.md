# Teklif: Sektörel Hareketlilik ve Kapasite Tahmin Endeksi (Pro)

| | |
|---|---|
| **Hazırlayan** | Ebru Özpolat, Senior GRC Executive |
| **Hedef kitle** | Portföy yöneticileri ve makro hedge fon analistleri |
| **Tarih** | 1 Mayıs 2026 |
| **Ürün kotası** | Market Alpha (Pro) — bkz. [golden-standard-subscription-and-analytics.md](../golden-standard-subscription-and-analytics.md) |

> **Yasal uyarı:** Bu metin **tanıtım ve iç düzenleme** amaçlıdır. Uydu proxy özetleri **yatırım tavsiyesi, düzenleyici uygunluk beyanı veya hisse “short/long” tavsiyesi değildir**. Teknik feragat ve maskeleme politikası için tek kaynak: **[cco-audit-methodology.md](../cco-audit-methodology.md)**.

---

## 1. Yönetici özeti: “Görünmeyeni modellemek”

Geleneksel borsa verileri ve KAP bildirimleri çoğunlukla **yayımlanmış geçmişe** odaklanır. **Market Alpha** paketi, Türkiye çimento sektöründe seçili üretim noktalarının **operasyonel performansını** Landsat 8/9 **Collection 2 Level-2** termal kanalı (`ST_B10`) ve Sentinel-5P **troposferik NO₂** (ör. OFFL **L3** ürün çizgisi) ile **anlık veya yüksek sıklıkta** izlenebilir bir proxy olarak sunar.

Resmi finansal tabloların yayımlanma döngüsüne kıyasla uydu gözlemleri **farklı bir zaman çözünürlüğü** sağlar; “aylar önce” ifadesi **tesis, rapor tarihi ve veri penceresine bağlı bir örnek senaryodur**, garanti edilen bir öncülük süresi değildir.

---

## 2. Karar destek metrikleri (benchmark analizi)

Ham uydu çıktıları, şeffaf bir çerçevede **Tahmini Üretim Kapasitesi** proxy’sine ölçeklenir (`app/scoring/capacity_proxy.py`: 15 °C altı ~0 %, referans **20.11 °C** → 100 %).

| Tesis | Isı imzası (proxy) | Tahmini kapasite (proxy) | Sinyal durumu (yorum) |
|--------|-------------------|---------------------------|------------------------|
| Çimsa Afyon | 20.11 °C | **100.00%** (baz çizgisi) | Stabil üretim (proxy) |
| Limak Balıkesir | 20.06 °C | **99.02%** | Tam kapasiteye yakın (proxy); Çimsa’dan **0.98 yüzde puanı** geride |
| Akçansa Çanakkale | 19.25 °C | **83.17%** | Olası operasyonel yavaşlama veya planlı duruş / bakım hipotezi (proxy) |

**Yuvarlama ve alternatif gösterim**

- **Kurumsal / benchmark tablosu (önerilen):** Kapasite **`estimate_capacity` çıktısı ile aynı iki ondalık** gösterilir (örn. Limak **99.02%** vs Çimsa **100.00%**). **0.02 p.p.** bile rakip sıralamasında ve spread analizinde anlamlı olabilir.
- **İletişim / slayt (alternatif):** Tek ondalık veya `≈` önekli kısaltma (örn. “≈83.2%”) yalnızca okunabilirlik içindir; **sözleşme, CSV ve model beslemesi için iki ondalık değer esas alınır.**

**Alfa sinyali (hipotetik çerçeve):** Akçansa için **83.17%** kapasite proxy’si, rakip tesislere kıyasla **erken uyarı** veya senaryo analizi için kullanılabilir; **nedensellik, bakım takvimi veya üretim tonajı doğrulaması** saha ve şirket verisi olmadan çıkarılmaz. “Short”, “re-weight” veya pozisyon kararı **yalnızca müşteri risk politikası** çerçevesindedir; GeoRisk Engine **bu kararları önermez**.

---

## 3. Metodolojik güven ve GRC mührü

Üretilen çıktılar yalnızca “ham sayı” değil, **CCO hizası mühürlü** operasyonel doğrulama akışına bağlanır:

- **Bağımsızlık:** Veriler Google Earth Engine üzerinden türetilir; şirket beyanına **bağımlı değildir** (ancak yer doğrulaması ve AOI’nin doğru seçildiği müşteri sorumluluğunda önerilir).
- **Doğrulama:** Termalde **QA_PIXEL** bulut/gölge maskeleme politikası; NO₂ tarafında üretimde kullanılan **L3** çizgisi ve ilgili kalite notları **[cco-audit-methodology.md](../cco-audit-methodology.md)** ile hizalanır.
- **Yasal zırh:** Tüm dağıtımlar feragat ve metodoloji referanslarıyla sunulur; detaylı şablon ve snippet’ler repo içi `docs/turkiye/` altında tutulur.

---

## 4. Abonelik ve teslimat

| Öğe | Açıklama |
|-----|-----------|
| **Erişim** | Canlı dashboard (`scripts/audit_dashboard.py`) + aylık mühürlü analiz raporu üretim hattı |
| **Format** | PDF (kurumsal sunum) ve CSV / Excel dışa aktarım (Pro kapsamında ürünleştirilmeli) |
| **Örnek fiyat (bu teklif)** | Sektörel paket (**3 ana tesis**) için **USD 25.000 / yıl** (gösterge; kontrat ve vergi hariç) |

Geniş paket aralıkları için bkz. [golden-standard-subscription-and-analytics.md](../golden-standard-subscription-and-analytics.md) §3.

---

## Sunum notu (hedge fon brifingi — örnek cümle)

> “Akçansa pozisyonu taşıyan bir fon, tesiste ilişkilendirilen termal proxy’nin **19.25 °C** bandına indiğini ve bunun demo modelde **%83.17 Tahmini Üretim Kapasitesi** (iki ondalık; slaytta kısaltılarak ≈83.2% da sunulabilir) anlamına geldiğini görünür kılmıyorsa, operasyonel görünürlük açısından bir **erken uyarı katmanı** eksik kalabilir. Bu panel, metodolojisi mühürlenmiş uydu proxy’si ile bu görünürlüğü artırmayı hedefler — yine de **tek başına yatırım kararı yerine geçmez**.”

---

## İlgili teknik yollar

- Metodoloji: [cco-audit-methodology.md](../cco-audit-methodology.md)  
- Fiyatlandırma ve alternatif veri anlatısı: [golden-standard-subscription-and-analytics.md](../golden-standard-subscription-and-analytics.md)  
- Dashboard: `scripts/audit_dashboard.py` · Kapasite proxy: `app/scoring/capacity_proxy.py`
