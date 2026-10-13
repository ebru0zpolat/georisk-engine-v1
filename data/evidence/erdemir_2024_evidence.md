# GeoRisk Validation Evidence — Ereğli Demir ve Çelik Fab. (Erdemir) — TSRS 2025 doğrulama

- **Case:** `erdemir_2024`
- **GeoRisk version:** georisk-engine-v0.1
- **Schema version:** 1.0
- **Generated at:** 2025-05-03 00:00:00+00:00
- **Records:** 10
- **Flag rollup:** 🟢 5 · 🟡 5 · 🔴 0 · ⚪ 0

> GeoRisk üretilen şirket beyanlarını yeniden üretmez; bağımsız sinyaller üretip
> sapmayı işaretler. Her kayıt; raporlanan metrik kaynağına, GeoRisk sinyal kaynağına,
> uygulanan metodolojiye ve sonuç bayrağına kadar izlenebilir.

## Evidence records
### `ERD-2024-PROD-001` — crude_steel_production_ton 🟢 Green
- **Reported:** 8,089,587 ton — Erdemir TSRS 2025, Üretim Tablosu (assurance: limited)
- **GeoRisk signal:** 8,350,000 ton — Sentinel-5P / VIIRS thermal index (Ereğli + İskenderun) (`S5P-OFFL-L3 / VNP46A2 2024`, confidence 0.58)
- **Methodology:** Thermal activity → sectoral production estimate — `thermal_index → BOF production estimate`; threshold: ±15% green; 15–40% amber; >40% red
- **Divergence:** -3.12%
- **Outcome:** Üretim proxy'si raporlanan tonajın ±15% bandında; yönsel tutarlı.
- *Methodology note (TR):* İki tesisin termal aktivite indeksinden üretim tahmini; proxy doğası gereği orta güven.

### `ERD-2024-INT-001` — scope_1_2_emission_intensity_2025 🟡 Amber
- **Reported:** 2.198 tCO2e/ton — Erdemir TSRS 2025, İklim Bölümü (assurance: limited)
- **GeoRisk signal:** 2.1 tCO2e/ton — World Steel 2024 BOF intensity benchmark (`World Steel 2024`, confidence 0.72)
- **Methodology:** Emission intensity divergence — `(reported - benchmark) / benchmark`; threshold: ±15% green; 2024→2025 ölçüm esası değiştiği için yıl trendi okunamaz → karşılaştırılabilirlik boşluğu, amber
- **Divergence:** 4.67%
- **Outcome:** Yoğunluk benchmark'ın +4.7% üzerinde; ±15% bandında ama 2024→2025 ölçüm esası değiştiği için yıl trendi doğrulanamıyor, karşılaştırılabilirlik boşluğu nedeniyle amber.
- *Methodology note (TR):* 2025 yoğunluğu benchmark'a göre tek yıl olarak değerlendirilir. 2024 ve 2025 rakamları farklı ölçüm esasıyla raporlandığı için 2024→2025 değişimi 'kötüleşme' veya 'iyileşme' olarak yorumlanamaz; trend ancak şirket yeniden ifade edilmiş (restated) 2024 rakamı açıklarsa kurulabilir.

### `ERD-2024-INT-002` — scope_1_2_emission_intensity_2024 🟡 Amber
- **Reported:** 2.131 tCO2e/ton — Erdemir TSRS 2025, İklim Bölümü (2024 karşılaştırma) (assurance: limited)
- **GeoRisk signal:** 2.1 tCO2e/ton — World Steel 2024 BOF intensity benchmark (`World Steel 2024`, confidence 0.72)
- **Methodology:** Emission intensity divergence (prior-year figure, different measurement basis) — `(reported - benchmark) / benchmark`; threshold: ±15% green; 2025 ile aynı esasta olmadığı için trend tabanı olarak kullanılamaz → karşılaştırılabilirlik boşluğu, amber
- **Divergence:** 1.48%
- **Outcome:** 2024 yoğunluğu benchmark'ın +1.5% üzerinde; 2025 ile ölçüm esası farklı olduğundan trend tabanı olarak kullanılamaz, karşılaştırılabilirlik boşluğu nedeniyle amber.
- *Methodology note (TR):* 2024 yoğunluğu benchmark'a yakın (+1.5%). Bu rakam 2025 raporundaki karşılaştırma sütunundan alınmıştır ve 2025 ile aynı ölçüm esasında değildir; 2025 için trend tabanı olarak kullanılmaz.

### `ERD-2024-SCOPE2-001` — scope_2_implied_grid_emission_factor 🟢 Green
- **Reported:** 0.42 tCO2e/MWh — Erdemir TSRS 2025, Kapsam 2 dipnotundan türetildi (assurance: limited)
- **GeoRisk signal:** 0.44 tCO2e/MWh — TEİAŞ / IEA Turkey grid emission factor (`IEA Turkey 2024`, confidence 0.65)
- **Methodology:** Grid factor × tüketilen elektrik çapraz kontrol — `grid_factor × consumed_electricity`; threshold: ±15% green; 15–40% amber; >40% red
- **Divergence:** -4.55%
- **Outcome:** Örtük şebeke faktörü ulusal faktörün -4.5% altında; ±15% bandında, green.
- *Methodology note (TR):* Raporlanan örtük şebeke faktörü ulusal IEA/TEİAŞ faktörüyle tutarlı.

### `ERD-2024-WATER-001` — water_stress_exposure_consolidated_pct 🟢 Green
- **Reported:** 56 % — Erdemir TSRS 2025, Su Stresi (WRI Aqueduct'a geçiş) (assurance: limited)
- **GeoRisk signal:** 58.5 % — WRI Aqueduct su stresi katmanı (Ereğli + İskenderun, ağırlıklı) (`WRI Aqueduct 4.0`, confidence 0.8)
- **Methodology:** Lokasyon bazlı su stresi (WRI Aqueduct — şirketle aynı metodoloji) — `weighted(Ereğli, İskenderun) Aqueduct stress`; threshold: ±15% green; metodoloji uyumu güveni artırır
- **Divergence:** -4.27%
- **Outcome:** Konsolide su stresi Aqueduct sinyaliyle ±15% içinde; aynı metodoloji, yüksek güven, green.
- *Methodology note (TR):* Erdemir 2025'te WRI Aqueduct metodolojisine geçti; doğrudan karşılaştırma yapılabilir. 2024 verisi eski Türkiye yönetmeliğiyle ölçülmüş olabilir → yıl karşılaştırmasında metodoloji notu.

### `ERD-2024-WATER-002` — water_stress_eregli_pct 🟡 Amber
- **Reported:** — % — Erdemir TSRS 2025 — yalnızca konsolide oran açıklanmış (assurance: none)
- **GeoRisk signal:** 30 % — WRI Aqueduct (Ereğli / Karadeniz) (`WRI Aqueduct 4.0`, confidence 0.78)
- **Methodology:** Lokasyon bazlı ayrıştırma (Ereğli) — `Aqueduct stress @ Ereğli`; threshold: veri kaynağı boşluğu → amber
- **Divergence:** —
- **Outcome:** GeoRisk Ereğli için düşük-orta stres üretiyor; şirket lokasyon ayrıştırması açıklamadığı için karşılaştırılabilir raporlanan değer yok (veri boşluğu), amber.
- *Methodology note (TR):* Ereğli düşük-orta su stresi bölgesi; şirket konsolide oran arkasındaki driver'ı açıklamıyor.

### `ERD-2024-WATER-003` — water_stress_iskenderun_pct 🟡 Amber
- **Reported:** — % — Erdemir TSRS 2025 — yalnızca konsolide oran açıklanmış (assurance: none)
- **GeoRisk signal:** 82 % — WRI Aqueduct (İskenderun / Doğu Akdeniz, Hatay) (`WRI Aqueduct 4.0`, confidence 0.78)
- **Methodology:** Lokasyon bazlı ayrıştırma (İskenderun) — `Aqueduct stress @ İskenderun`; threshold: veri kaynağı boşluğu → amber
- **Divergence:** —
- **Outcome:** İskenderun yüksek stres bölgesi ve konsolide oranın asıl sürücüsü; şirket ayrıştırma açıklamadığı için karşılaştırılabilir değer yok, amber (validation value: driver şeffaflığı).
- *Methodology note (TR):* İskenderun yüksek su stresi bölgesi; konsolide %56'nın driver'ı İskenderun ağırlığıdır.

### `ERD-2024-CBAM-001` — cbam_ebitda_impact_mid_pct 🟢 Green
- **Reported:** 2 % — Erdemir TSRS 2025, Bölüm 4.1.1 (SKDM Etki Modeli, orta vade) (assurance: none)
- **GeoRisk signal:** 2.15 % — GeoRisk CBAM proxy / EBITDA (ETS €65/ton orta senaryo) (`EU CBAM Phase 1 + EU ETS 2025-Q1`, confidence 0.6)
- **Methodology:** CBAM proxy FAVÖK etkisi divergence — `CBAM_proxy_exposure / EBITDA`; threshold: bant içinde tutarlı → green; >20% sapma → amber; yönsel tutarsızlık → red
- **Divergence:** -6.98%
- **Outcome:** GeoRisk FAVÖK etki oranı (%2,15) Erdemir'in raporlanan bandının içinde; +7.5% sapma, green.
- *Methodology note (TR):* GeoRisk proxy oranı Erdemir'in %1,6–2,4 bandının içinde (orta vade %2,0'a yakın).

### `ERD-2024-CBAM-002` — cbam_absolute_exposure_eur 🟡 Amber
- **Reported:** — EUR — Erdemir TSRS 2025 — mutlak SKDM maruziyeti açıklanmadı (yalnızca FAVÖK %) (assurance: none)
- **GeoRisk signal:** 393,315,720 EUR — GeoRisk CBAM proxy (8.089.587 × (2.198−1.45) × ETS), orta senaryo €65/ton (`EU CBAM Phase 1 + EU ETS 2025-Q1`, confidence 0.6)
- **Methodology:** CBAM proxy mutlak maruziyet — `tonnage × (intensity − free_allocation) × ETS_price`; threshold: karşılaştırılabilir raporlanan değer yok → amber
- **Divergence:** —
- **Outcome:** GeoRisk ~€394M mutlak maruziyet üretiyor; şirket yalnızca FAVÖK % açıkladığı için mutlak değerde karşılaştırma boşluğu, amber.
- *Methodology note (TR):* Senaryo bandı €303M (€50) – €394M (€65) – €485M (€80). Şirket mutlak maruziyeti açıklamadığı için doğrudan kıyas yapılamaz.

### `ERD-2024-FUEL-001` — fuel_mix_coal_share_pct 🟢 Green
- **Reported:** 88 % — Erdemir TSRS 2025, Enerji Karması (kömür %88 / gaz %12) (assurance: limited)
- **GeoRisk signal:** 86 % — Geospatial yakıt altyapısı varlığı (kömür terminali + tesis topolojisi) (`GeoRisk fuel infra layer 2024`, confidence 0.5)
- **Methodology:** Yakıt mix plausibility — `infra-derived coal share vs reported`; threshold: ±15% green; 15–40% amber; >40% red
- **Divergence:** 2.33%
- **Outcome:** Altyapı bazlı kömür payı (%86) raporlanan %88 ile ±15% içinde; makul, green.
- *Methodology note (TR):* BOF ağırlıklı tesiste yüksek kömür payı altyapı varlığıyla makul; düşük güvenli proxy.
