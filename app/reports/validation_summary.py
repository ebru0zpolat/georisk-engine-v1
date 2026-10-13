"""Audit summary markdown rendered from a validation :class:`EvidenceTrail`."""

from __future__ import annotations

from app.schemas.validation import DivergenceFlag, EvidenceRecord, EvidenceTrail

_FLAG_BADGE = {
    DivergenceFlag.GREEN: "🟢 Green",
    DivergenceFlag.AMBER: "🟡 Amber",
    DivergenceFlag.RED: "🔴 Red",
    DivergenceFlag.NO_SIGNAL: "⚪ No signal",
}


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    # Whole numbers render with thousands separators (e.g. tonnage, EUR exposure);
    # fractional values keep up to 3 decimals without scientific notation.
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _record_block(rec: EvidenceRecord) -> str:
    rm = rec.reported_metric
    gs = rec.georisk_signal
    md = rec.methodology
    notes = f"\n- *Methodology note (TR):* {md.notes_tr}" if md.notes_tr else ""
    return f"""### `{rec.validation_id}` — {rm.field} {_FLAG_BADGE[rec.flag]}
- **Reported:** {_fmt(rm.value)} {rm.unit or ''} — {rm.source} (assurance: {rm.assurance})
- **GeoRisk signal:** {_fmt(gs.value)} {gs.unit or ''} — {gs.source} (`{gs.source_version}`, confidence {gs.confidence:g})
- **Methodology:** {md.method} — `{md.formula or 'n/a'}`; threshold: {md.threshold}
- **Divergence:** {_fmt(rec.divergence_pct)}{'%' if rec.divergence_pct is not None else ''}
- **Outcome:** {rec.explanation}{notes}
"""


def build_validation_summary_markdown(trail: EvidenceTrail) -> str:
    """Render the full audit summary for a benchmark evidence trail."""
    counts = trail.summary_counts()
    counts_line = (
        f"🟢 {counts['green']} · 🟡 {counts['amber']} · "
        f"🔴 {counts['red']} · ⚪ {counts['no_signal']}"
    )
    records = "\n".join(_record_block(rec) for rec in trail.records)
    return f"""# GeoRisk Validation Evidence — {trail.subject_tr}

- **Case:** `{trail.case_id}`
- **GeoRisk version:** {trail.georisk_version}
- **Schema version:** {trail.schema_version}
- **Generated at:** {trail.generated_at}
- **Records:** {len(trail.records)}
- **Flag rollup:** {counts_line}

> GeoRisk üretilen şirket beyanlarını yeniden üretmez; bağımsız sinyaller üretip
> sapmayı işaretler. Her kayıt; raporlanan metrik kaynağına, GeoRisk sinyal kaynağına,
> uygulanan metodolojiye ve sonuç bayrağına kadar izlenebilir.

## Evidence records
{records}"""
