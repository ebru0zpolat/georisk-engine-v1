# Trafo — Primary Audit & ESG Watch

Bu klasör, çimento `audit_dashboard.py` hattına **ikinci dikey** olarak konumlanan **trafo / güç ekipmanı** emisyon doğrulama çıktılarını ve metinlerini içerir.

## Birincil denetim (Primary Audit) tesileri

- **Astor Enerji (Ankara)** — büyük kapalı alan ve sevkiyat trafiği bağlamı.  
- **BEST - Balıkesir Elektromekanik (Balıkesir)** — yüksek gerilim hattı; Scope 2 yoğunluğu için NO₂ + gece ışığı çapraz sorgusu.

AOI: `primary_audit_facilities.geojson` *(poligonlar örnek OSB koordinatlarıdır; sahada doğrulanmalıdır).*

**Yol haritası:** Hitachi Energy (Kocaeli) gibi küresel tedarik zinciri odaklı tesisler ek Primary/Institutional paketlerle genişletilebilir.

## Komutlar

```bash
# Mock (EE gerekmez)
AUDIT_USE_MOCK=true python scripts/transformer_audit.py --all

# Tek tesis
AUDIT_USE_MOCK=true python scripts/transformer_audit.py --facility astor_enerji_ankara
```

Mühürlü Markdown: `sealed_reports/{facility_id}_{YYYYMMDD}.md` — gövdede `git rev-parse HEAD` özeti.

## Metinler

- Metodoloji: [transformer-audit-methodology.md](./transformer-audit-methodology.md)  
- ESG matrisi: [esg-emisyon-matrisi.md](./esg-emisyon-matrisi.md)  
- Proprietary (sevkiyat → kapasite katsayıları): [../proprietary-transformer-logistics-capacity-proxy.md](../proprietary-transformer-logistics-capacity-proxy.md)  
- Mühürlü operasyonel endeks, QOR, kapalı devre, filigran: [../georisk-sealed-index-closed-loop-publishing.md](../georisk-sealed-index-closed-loop-publishing.md)  
- Birincil sektör öncelikleri (SKDM): [../sectors-skdm-primary-priorities.md](../sectors-skdm-primary-priorities.md)  
- Veri kabul standardı (trafo): [../standards/transformer-data-acceptance-and-processing.md](../standards/transformer-data-acceptance-and-processing.md) · Çeyrek arşivi: [../../data/archive/README.md](../../data/archive/README.md)
