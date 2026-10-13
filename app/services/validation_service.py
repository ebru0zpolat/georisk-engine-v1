"""Build the audit-ready evidence trail for GeoRisk vs reported-metric validation.

GeoRisk does not reproduce company-reported figures; it generates independent
signals and flags divergence (GEO-121). :class:`ValidationService` turns the steel
sector comparisons for the Erdemir benchmark case into serialisable
:class:`EvidenceRecord` objects, each traceable to its reported-metric source,
GeoRisk signal source, methodology and outcome flag.

The Erdemir comparison inputs are the validated values carried by GEO-121
(steel-sector validation) and GEO-122 (CBAM exposure proxy).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import GeoRiskApiError
from app.reports.validation_summary import build_validation_summary_markdown
from app.schemas.validation import (
    BenchmarkRequest,
    DivergenceFlag,
    EvidenceRecord,
    EvidenceTrail,
    GeoRiskSignal,
    MethodologyRef,
    ReportedMetric,
    ValidationReport,
    ValidationResult,
    ValidationSummary,
    divergence_flag_to_validation,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVIDENCE_DIR = _REPO_ROOT / "data" / "evidence"

# Divergence thresholds (GEO-121 validation threshold rules).
_GREEN_MAX_PCT = 15.0
_AMBER_MAX_PCT = 40.0


def signed_divergence_pct(reported: float | None, signal: float | None) -> float | None:
    """Reported value's signed deviation from the independent GeoRisk signal, percent.

    ``(reported - signal) / signal * 100`` — positive means the company figure sits
    above the GeoRisk benchmark. Returns ``None`` when either side is missing or the
    signal is zero (no meaningful ratio).
    """
    if reported is None or signal is None or signal == 0:
        return None
    return round((reported - signal) / signal * 100.0, 2)


def classify(
    divergence_pct: float | None,
    *,
    directionally_consistent: bool = True,
    has_signal: bool = True,
) -> DivergenceFlag:
    """Map a divergence to a flag per the GEO-121 threshold rules.

    - GeoRisk cannot produce a signal → ``no_signal``.
    - Signal exists but no comparable reported value (data-source gap) → ``amber``.
    - Directional inconsistency → ``red`` if large, otherwise ``amber``.
    - Otherwise band by magnitude: ≤15% green, ≤40% amber, else red.
    """
    if not has_signal:
        return DivergenceFlag.NO_SIGNAL
    if divergence_pct is None:
        # Signal present but nothing comparable to diff against → data gap.
        return DivergenceFlag.AMBER
    mag = abs(divergence_pct)
    if not directionally_consistent:
        return DivergenceFlag.RED if mag > _GREEN_MAX_PCT else DivergenceFlag.AMBER
    if mag <= _GREEN_MAX_PCT:
        return DivergenceFlag.GREEN
    if mag <= _AMBER_MAX_PCT:
        return DivergenceFlag.AMBER
    return DivergenceFlag.RED


class _Comparison:
    """Internal spec for one Erdemir comparison before flag derivation."""

    def __init__(
        self,
        *,
        validation_id: str,
        reported: ReportedMetric,
        signal: GeoRiskSignal,
        methodology: MethodologyRef,
        explanation: str,
        directionally_consistent: bool = True,
        has_signal: bool = True,
    ) -> None:
        self.validation_id = validation_id
        self.reported = reported
        self.signal = signal
        self.methodology = methodology
        self.explanation = explanation
        self.directionally_consistent = directionally_consistent
        self.has_signal = has_signal


class ValidationService:
    """Generate, serialise, summarise and serve validation evidence trails."""

    def __init__(
        self,
        *,
        georisk_version: str | None = None,
        evidence_dir: Path | None = None,
    ) -> None:
        self.georisk_version = georisk_version or settings.georisk_version
        self.evidence_dir = evidence_dir or _EVIDENCE_DIR

    # -- record assembly -------------------------------------------------

    def _to_record(self, spec: _Comparison, *, generated_at: datetime) -> EvidenceRecord:
        divergence = signed_divergence_pct(spec.reported.value, spec.signal.value)
        flag = classify(
            divergence,
            directionally_consistent=spec.directionally_consistent,
            has_signal=spec.has_signal,
        )
        return EvidenceRecord(
            validation_id=spec.validation_id,
            reported_metric=spec.reported,
            georisk_signal=spec.signal,
            methodology=spec.methodology,
            divergence_pct=divergence,
            flag=flag,
            explanation=spec.explanation,
            georisk_version=self.georisk_version,
            generated_at=generated_at,
        )

    def build_erdemir_trail(self, *, generated_at: datetime | None = None) -> EvidenceTrail:
        """Build the full Erdemir 2024 evidence trail (≥8 validated fields)."""
        ts = generated_at or datetime.now(timezone.utc)
        records = [self._to_record(spec, generated_at=ts) for spec in _erdemir_comparisons()]
        return EvidenceTrail(
            case_id="erdemir_2024",
            subject_tr="Ereğli Demir ve Çelik Fab. (Erdemir) — TSRS 2025 doğrulama",
            georisk_version=self.georisk_version,
            generated_at=ts,
            records=records,
        )

    # -- export ----------------------------------------------------------

    def export_trail_json(
        self,
        trail: EvidenceTrail,
        *,
        path: Path | None = None,
    ) -> Path:
        """Write ``trail`` to a JSON file; defaults to ``data/evidence/<case_id>_evidence.json``."""
        out = path or (_EVIDENCE_DIR / f"{trail.case_id}_evidence.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(trail.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return out

    def export_summary_markdown(
        self,
        trail: EvidenceTrail,
        *,
        path: Path | None = None,
    ) -> Path:
        """Write the audit summary markdown; defaults to ``data/evidence/<case_id>_evidence.md``."""
        out = path or (_EVIDENCE_DIR / f"{trail.case_id}_evidence.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_validation_summary_markdown(trail), encoding="utf-8")
        return out

    # -- HTTP API (VAL-006) ----------------------------------------------

    def _evidence_path(self, company_id: str, reporting_year: int) -> Path:
        return self.evidence_dir / f"{company_id.lower()}_{reporting_year}_evidence.json"

    def _load_trail(self, company_id: str, reporting_year: int) -> EvidenceTrail:
        path = self._evidence_path(company_id, reporting_year)
        if not path.exists():
            raise GeoRiskApiError(
                code="validation_evidence_not_found",
                message=(
                    f"No validation evidence for company {company_id!r}, "
                    f"year {reporting_year}."
                ),
                status_code=404,
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "records" in payload:
            return EvidenceTrail.model_validate(payload)
        # Legacy VAL-006 fixture shape: ``results`` at top level.
        records = [
            EvidenceRecord(
                validation_id=row["validation_id"],
                reported_metric=ReportedMetric.model_validate(row["reported_metric"]),
                georisk_signal=GeoRiskSignal.model_validate(
                    {
                        **row["georisk_signal"],
                        "source_version": row["georisk_signal"].get(
                            "source_version",
                            payload.get("data_source_version", "unknown"),
                        ),
                    }
                ),
                methodology=MethodologyRef(
                    method="Persisted validation comparison",
                    threshold="See evidence trail methodology notes",
                ),
                divergence_pct=row.get("divergence_pct"),
                flag=DivergenceFlag(row["flag"]),
                explanation=row["explanation"],
                georisk_version=row.get("georisk_version", payload.get("georisk_version", "0.0.0")),
                generated_at=row.get("generated_at", payload.get("generated_at")),
            )
            for row in payload.get("results", [])
        ]
        case_id = payload.get("case_id") or f"{company_id.lower()}_{reporting_year}"
        return EvidenceTrail(
            case_id=case_id,
            subject_tr=payload.get("subject_tr", company_id),
            georisk_version=payload.get("georisk_version", "0.0.0"),
            generated_at=payload.get("generated_at") or datetime.now(timezone.utc),
            records=records,
        )

    @staticmethod
    def _result_from_record(record: EvidenceRecord) -> ValidationResult:
        divergence_pct = 0.0 if record.divergence_pct is None else float(record.divergence_pct)
        return ValidationResult.model_construct(
            validation_id=record.validation_id,
            reported_metric=record.reported_metric,
            georisk_signal=record.georisk_signal,
            divergence_pct=divergence_pct,
            flag=divergence_flag_to_validation(record.flag),
            explanation=record.explanation,
            georisk_version=record.georisk_version,
            data_source_version=record.georisk_signal.source_version,
            generated_at=record.generated_at,
        )

    def _report_from_trail(
        self,
        trail: EvidenceTrail,
        *,
        company_id: str,
        reporting_year: int,
        sector: str = "",
    ) -> ValidationReport:
        results = [self._result_from_record(record) for record in trail.records]
        return ValidationReport(
            company_id=company_id,
            reporting_year=reporting_year,
            sector=sector,
            results=results,
            summary=ValidationSummary.from_results(results),
            generated_at=trail.generated_at,
        )

    def benchmark(self, payload: BenchmarkRequest) -> ValidationReport:
        trail = self._load_trail(payload.company_id, payload.reporting_year)
        report = self._report_from_trail(
            trail,
            company_id=payload.company_id,
            reporting_year=payload.reporting_year,
            sector=payload.sector,
        )
        return report

    def get_report(self, company_id: str, reporting_year: int) -> ValidationReport:
        trail = self._load_trail(company_id, reporting_year)
        sector = "steel" if company_id.lower() == "erdemir" else ""
        return self._report_from_trail(
            trail,
            company_id=company_id,
            reporting_year=reporting_year,
            sector=sector,
        )

    def get_evidence(self, validation_id: str) -> ValidationResult:
        if not self.evidence_dir.exists():
            raise GeoRiskApiError(
                code="validation_evidence_not_found",
                message=f"No evidence record for validation_id {validation_id!r}.",
                status_code=404,
            )
        for path in sorted(self.evidence_dir.glob("*_evidence.json")):
            trail = EvidenceTrail.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for record in trail.records:
                if record.validation_id == validation_id:
                    return self._result_from_record(record)
        raise GeoRiskApiError(
            code="validation_evidence_not_found",
            message=f"No evidence record for validation_id {validation_id!r}.",
            status_code=404,
        )


def _erdemir_comparisons() -> list[_Comparison]:
    """Validated Erdemir comparisons (inputs from GEO-121 / GEO-122).

    Reported values reference the Erdemir TSRS 2025 report; GeoRisk signals are
    independent proxies derived from public datasets and satellite activity.
    """
    ets_mid_eur = 65.0  # ECB/ICE EU ETS snapshot assumption (mid scenario), 2025-Q1.
    net_cbam_intensity = 2.198 - 1.45  # = 0.748 net intensity after free allocation.
    crude_steel_ton = 8_089_587
    cbam_proxy_mid_eur = round(crude_steel_ton * net_cbam_intensity * ets_mid_eur)  # ≈ €394M

    return [
        # 1. Crude steel production proxy vs reported tonnage (thermal activity index).
        _Comparison(
            validation_id="ERD-2024-PROD-001",
            reported=ReportedMetric(
                field="crude_steel_production_ton",
                value=8_089_587,
                unit="ton",
                source="Erdemir TSRS 2025, Üretim Tablosu",
                assurance="limited",
            ),
            signal=GeoRiskSignal(
                type="satellite_thermal_production_proxy",
                value=8_350_000,
                unit="ton",
                source="Sentinel-5P / VIIRS thermal index (Ereğli + İskenderun)",
                source_version="S5P-OFFL-L3 / VNP46A2 2024",
                confidence=0.58,
            ),
            methodology=MethodologyRef(
                method="Thermal activity → sectoral production estimate",
                formula="thermal_index → BOF production estimate",
                threshold="±15% green; 15–40% amber; >40% red",
                notes_tr="İki tesisin termal aktivite indeksinden üretim tahmini; proxy doğası gereği orta güven.",
            ),
            explanation="Üretim proxy'si raporlanan tonajın ±15% bandında; yönsel tutarlı.",
        ),
        # 2. Scope 1+2 emission intensity 2025 vs World Steel BOF benchmark.
        _Comparison(
            validation_id="ERD-2024-INT-001",
            reported=ReportedMetric(
                field="scope_1_2_emission_intensity_2025",
                value=2.198,
                unit="tCO2e/ton",
                source="Erdemir TSRS 2025, İklim Bölümü",
                assurance="limited",
            ),
            signal=GeoRiskSignal(
                type="sectoral_emission_intensity_proxy",
                value=2.1,
                unit="tCO2e/ton",
                source="World Steel 2024 BOF intensity benchmark",
                source_version="World Steel 2024",
                confidence=0.72,
            ),
            methodology=MethodologyRef(
                method="Emission intensity divergence",
                formula="(reported - benchmark) / benchmark",
                threshold="±15% green; 2024→2025 ölçüm esası değiştiği için yıl trendi "
                "okunamaz → karşılaştırılabilirlik boşluğu, amber",
                notes_tr="2025 yoğunluğu benchmark'a göre tek yıl olarak değerlendirilir. "
                "2024 ve 2025 rakamları farklı ölçüm esasıyla raporlandığı için "
                "2024→2025 değişimi 'kötüleşme' veya 'iyileşme' olarak yorumlanamaz; "
                "trend ancak şirket yeniden ifade edilmiş (restated) 2024 rakamı açıklarsa kurulabilir.",
            ),
            directionally_consistent=False,
            explanation="Yoğunluk benchmark'ın +4.7% üzerinde; ±15% bandında ama 2024→2025 ölçüm "
            "esası değiştiği için yıl trendi doğrulanamıyor, karşılaştırılabilirlik boşluğu nedeniyle amber.",
        ),
        # 3. Scope 1+2 emission intensity 2024 (prior-year comparison column) vs benchmark.
        #    Not a trend baseline: the 2024 and 2025 figures are on different measurement
        #    bases, so the pair must not be read as a year-over-year direction.
        _Comparison(
            validation_id="ERD-2024-INT-002",
            reported=ReportedMetric(
                field="scope_1_2_emission_intensity_2024",
                value=2.131,
                unit="tCO2e/ton",
                source="Erdemir TSRS 2025, İklim Bölümü (2024 karşılaştırma)",
                assurance="limited",
            ),
            signal=GeoRiskSignal(
                type="sectoral_emission_intensity_proxy",
                value=2.1,
                unit="tCO2e/ton",
                source="World Steel 2024 BOF intensity benchmark",
                source_version="World Steel 2024",
                confidence=0.72,
            ),
            methodology=MethodologyRef(
                method="Emission intensity divergence (prior-year figure, different measurement basis)",
                formula="(reported - benchmark) / benchmark",
                threshold="±15% green; 2025 ile aynı esasta olmadığı için trend tabanı olarak "
                "kullanılamaz → karşılaştırılabilirlik boşluğu, amber",
                notes_tr="2024 yoğunluğu benchmark'a yakın (+1.5%). Bu rakam 2025 raporundaki "
                "karşılaştırma sütunundan alınmıştır ve 2025 ile aynı ölçüm esasında değildir; "
                "2025 için trend tabanı olarak kullanılmaz.",
            ),
            directionally_consistent=False,
            explanation="2024 yoğunluğu benchmark'ın +1.5% üzerinde; 2025 ile ölçüm esası farklı olduğundan "
            "trend tabanı olarak kullanılamaz, karşılaştırılabilirlik boşluğu nedeniyle amber.",
        ),
        # 4. Scope 2 grid emission factor cross-check (TEİAŞ / IEA Turkey).
        _Comparison(
            validation_id="ERD-2024-SCOPE2-001",
            reported=ReportedMetric(
                field="scope_2_implied_grid_emission_factor",
                value=0.42,
                unit="tCO2e/MWh",
                source="Erdemir TSRS 2025, Kapsam 2 dipnotundan türetildi",
                assurance="limited",
            ),
            signal=GeoRiskSignal(
                type="grid_emission_factor_crosscheck",
                value=0.44,
                unit="tCO2e/MWh",
                source="TEİAŞ / IEA Turkey grid emission factor",
                source_version="IEA Turkey 2024",
                confidence=0.65,
            ),
            methodology=MethodologyRef(
                method="Grid factor × tüketilen elektrik çapraz kontrol",
                formula="grid_factor × consumed_electricity",
                threshold="±15% green; 15–40% amber; >40% red",
                notes_tr="Raporlanan örtük şebeke faktörü ulusal IEA/TEİAŞ faktörüyle tutarlı.",
            ),
            explanation="Örtük şebeke faktörü ulusal faktörün -4.5% altında; ±15% bandında, green.",
        ),
        # 5. Consolidated water stress vs WRI Aqueduct (same methodology — direct compare).
        _Comparison(
            validation_id="ERD-2024-WATER-001",
            reported=ReportedMetric(
                field="water_stress_exposure_consolidated_pct",
                value=56.0,
                unit="%",
                source="Erdemir TSRS 2025, Su Stresi (WRI Aqueduct'a geçiş)",
                assurance="limited",
            ),
            signal=GeoRiskSignal(
                type="wri_aqueduct_water_stress_consolidated",
                value=58.5,
                unit="%",
                source="WRI Aqueduct su stresi katmanı (Ereğli + İskenderun, ağırlıklı)",
                source_version="WRI Aqueduct 4.0",
                confidence=0.80,
            ),
            methodology=MethodologyRef(
                method="Lokasyon bazlı su stresi (WRI Aqueduct — şirketle aynı metodoloji)",
                formula="weighted(Ereğli, İskenderun) Aqueduct stress",
                threshold="±15% green; metodoloji uyumu güveni artırır",
                notes_tr="Erdemir 2025'te WRI Aqueduct metodolojisine geçti; doğrudan karşılaştırma yapılabilir. "
                "2024 verisi eski Türkiye yönetmeliğiyle ölçülmüş olabilir → yıl karşılaştırmasında metodoloji notu.",
            ),
            explanation="Konsolide su stresi Aqueduct sinyaliyle ±15% içinde; aynı metodoloji, yüksek güven, green.",
        ),
        # 6. Water stress — Ereğli (location decomposition; company discloses only consolidated).
        _Comparison(
            validation_id="ERD-2024-WATER-002",
            reported=ReportedMetric(
                field="water_stress_eregli_pct",
                value=None,
                unit="%",
                source="Erdemir TSRS 2025 — yalnızca konsolide oran açıklanmış",
                assurance="none",
            ),
            signal=GeoRiskSignal(
                type="wri_aqueduct_water_stress_eregli",
                value=30.0,
                unit="%",
                source="WRI Aqueduct (Ereğli / Karadeniz)",
                source_version="WRI Aqueduct 4.0",
                confidence=0.78,
            ),
            methodology=MethodologyRef(
                method="Lokasyon bazlı ayrıştırma (Ereğli)",
                formula="Aqueduct stress @ Ereğli",
                threshold="veri kaynağı boşluğu → amber",
                notes_tr="Ereğli düşük-orta su stresi bölgesi; şirket konsolide oran arkasındaki driver'ı açıklamıyor.",
            ),
            has_signal=True,
            explanation="GeoRisk Ereğli için düşük-orta stres üretiyor; şirket lokasyon ayrıştırması açıklamadığı "
            "için karşılaştırılabilir raporlanan değer yok (veri boşluğu), amber.",
        ),
        # 7. Water stress — İskenderun (high-stress driver behind consolidated 56%).
        _Comparison(
            validation_id="ERD-2024-WATER-003",
            reported=ReportedMetric(
                field="water_stress_iskenderun_pct",
                value=None,
                unit="%",
                source="Erdemir TSRS 2025 — yalnızca konsolide oran açıklanmış",
                assurance="none",
            ),
            signal=GeoRiskSignal(
                type="wri_aqueduct_water_stress_iskenderun",
                value=82.0,
                unit="%",
                source="WRI Aqueduct (İskenderun / Doğu Akdeniz, Hatay)",
                source_version="WRI Aqueduct 4.0",
                confidence=0.78,
            ),
            methodology=MethodologyRef(
                method="Lokasyon bazlı ayrıştırma (İskenderun)",
                formula="Aqueduct stress @ İskenderun",
                threshold="veri kaynağı boşluğu → amber",
                notes_tr="İskenderun yüksek su stresi bölgesi; konsolide %56'nın driver'ı İskenderun ağırlığıdır.",
            ),
            has_signal=True,
            explanation="İskenderun yüksek stres bölgesi ve konsolide oranın asıl sürücüsü; şirket ayrıştırma "
            "açıklamadığı için karşılaştırılabilir değer yok, amber (validation value: driver şeffaflığı).",
        ),
        # 8. CBAM EBITDA impact vs Erdemir's own SKDM model band (GEO-122).
        _Comparison(
            validation_id="ERD-2024-CBAM-001",
            reported=ReportedMetric(
                field="cbam_ebitda_impact_mid_pct",
                value=2.0,
                unit="%",
                source="Erdemir TSRS 2025, Bölüm 4.1.1 (SKDM Etki Modeli, orta vade)",
                assurance="none",
            ),
            signal=GeoRiskSignal(
                type="cbam_proxy_ebitda_ratio",
                value=2.15,
                unit="%",
                source="GeoRisk CBAM proxy / EBITDA (ETS €65/ton orta senaryo)",
                source_version="EU CBAM Phase 1 + EU ETS 2025-Q1",
                confidence=0.60,
            ),
            methodology=MethodologyRef(
                method="CBAM proxy FAVÖK etkisi divergence",
                formula="CBAM_proxy_exposure / EBITDA",
                threshold="bant içinde tutarlı → green; >20% sapma → amber; yönsel tutarsızlık → red",
                notes_tr="GeoRisk proxy oranı Erdemir'in %1,6–2,4 bandının içinde (orta vade %2,0'a yakın).",
            ),
            explanation="GeoRisk FAVÖK etki oranı (%2,15) Erdemir'in raporlanan bandının içinde; +7.5% sapma, green.",
        ),
        # 9. CBAM proxy absolute exposure — GeoRisk-generated, not disclosed by company.
        _Comparison(
            validation_id="ERD-2024-CBAM-002",
            reported=ReportedMetric(
                field="cbam_absolute_exposure_eur",
                value=None,
                unit="EUR",
                source="Erdemir TSRS 2025 — mutlak SKDM maruziyeti açıklanmadı (yalnızca FAVÖK %)",
                assurance="none",
            ),
            signal=GeoRiskSignal(
                type="cbam_proxy_exposure_eur",
                value=float(cbam_proxy_mid_eur),
                unit="EUR",
                source="GeoRisk CBAM proxy (8.089.587 × (2.198−1.45) × ETS), orta senaryo €65/ton",
                source_version="EU CBAM Phase 1 + EU ETS 2025-Q1",
                confidence=0.60,
            ),
            methodology=MethodologyRef(
                method="CBAM proxy mutlak maruziyet",
                formula="tonnage × (intensity − free_allocation) × ETS_price",
                threshold="karşılaştırılabilir raporlanan değer yok → amber",
                notes_tr="Senaryo bandı €303M (€50) – €394M (€65) – €485M (€80). "
                "Şirket mutlak maruziyeti açıklamadığı için doğrudan kıyas yapılamaz.",
            ),
            has_signal=True,
            explanation="GeoRisk ~€394M mutlak maruziyet üretiyor; şirket yalnızca FAVÖK % açıkladığı için "
            "mutlak değerde karşılaştırma boşluğu, amber.",
        ),
        # 10. Fuel mix plausibility (geospatial fuel infrastructure presence).
        _Comparison(
            validation_id="ERD-2024-FUEL-001",
            reported=ReportedMetric(
                field="fuel_mix_coal_share_pct",
                value=88.0,
                unit="%",
                source="Erdemir TSRS 2025, Enerji Karması (kömür %88 / gaz %12)",
                assurance="limited",
            ),
            signal=GeoRiskSignal(
                type="geospatial_fuel_infrastructure_plausibility",
                value=86.0,
                unit="%",
                source="Geospatial yakıt altyapısı varlığı (kömür terminali + tesis topolojisi)",
                source_version="GeoRisk fuel infra layer 2024",
                confidence=0.50,
            ),
            methodology=MethodologyRef(
                method="Yakıt mix plausibility",
                formula="infra-derived coal share vs reported",
                threshold="±15% green; 15–40% amber; >40% red",
                notes_tr="BOF ağırlıklı tesiste yüksek kömür payı altyapı varlığıyla makul; düşük güvenli proxy.",
            ),
            explanation="Altyapı bazlı kömür payı (%86) raporlanan %88 ile ±15% içinde; makul, green.",
        ),
    ]
