"""Parse portfolio CSV and GeoJSON uploads into ``PortfolioUploadRequest``."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError

from app.schemas.adaptation import AdaptationOutcome, MeasureStatus
from app.schemas.portfolio import (
    PORTFOLIO_MAX_ASSETS,
    PortfolioUploadRequest,
    UniversalAsset,
)

_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "asset_id": ("asset_id", "id", "asset"),
    "address": ("address", "street_address", "full_address"),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "lng"),
    "asset_value": ("asset_value", "value", "collateral_value"),
    "building_type": ("building_type", "building", "structure_type"),
    "use_class": ("use_class", "use", "occupancy"),
    "construction_year": ("construction_year", "year_built", "built_year"),
    "floors": ("floors", "num_floors", "storeys", "stories"),
    "insurance_coverage": ("insurance_coverage", "insured_amount", "insurance"),
    "existing_adaptation_measures": (
        "existing_adaptation_measures",
        "adaptation_measures",
        "existing_measures",
    ),
    "ltv": ("ltv", "loan_to_value"),
    "loan_id": ("loan_id", "loan", "collateral_id"),
    "measure_id": ("measure_id",),
    "measure_status": ("measure_status", "adaptation_status"),
    "implemented_date": ("implemented_date",),
    "post_implementation_review": ("post_implementation_review", "pir"),
    "share_outcome_consented": ("share_outcome_consented", "outcome_consent"),
    "anonymise_in_aggregate": ("anonymise_in_aggregate", "anonymize_in_aggregate"),
}


def _norm_header(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def _build_header_map(fieldnames: list[str] | None) -> dict[str, str]:
    if not fieldnames:
        raise ValueError("CSV has no header row.")
    present = {_norm_header(h): h for h in fieldnames if h and h.strip()}
    mapping: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in present:
                mapping[canonical] = present[alias]
                break
    return mapping


def _cell(row: dict[str, Any], header_map: dict[str, str], canonical: str) -> str | None:
    key = header_map.get(canonical)
    if key is None:
        return None
    raw = row.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    return text if text != "" else None


def _parse_bool(raw: str | None, *, default: bool | None = None) -> bool | None:
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "y", "t"}:
        return True
    if lowered in {"0", "false", "no", "n", "f"}:
        return False
    raise ValueError(f"Invalid boolean value: {raw!r}")


def _parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    text = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"Invalid date: {raw!r}") from exc


def _parse_float(raw: str | float | int | None) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return float(str(raw).replace(",", ""))


def _parse_int(raw: str | int | None) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return raw
    return int(float(str(raw).replace(",", "")))


def _parse_measures(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    parts = [p.strip() for p in str(raw).replace(";", "|").split("|")]
    return [p for p in parts if p]


def _adaptation_from_flat(get: Any) -> AdaptationOutcome | None:
    """Build AdaptationOutcome from a getter ``(canonical) -> value``."""
    status_raw = get("measure_status")
    measure_status = None
    if status_raw not in (None, ""):
        measure_status = MeasureStatus(str(status_raw).strip())

    implemented = get("implemented_date")
    if isinstance(implemented, date):
        implemented_date = implemented
    else:
        implemented_date = _parse_date(str(implemented) if implemented not in (None, "") else None)

    share_raw = get("share_outcome_consented")
    anon_raw = get("anonymise_in_aggregate")
    share = _parse_bool(str(share_raw) if share_raw not in (None, "") else None, default=False)
    anon = _parse_bool(str(anon_raw) if anon_raw not in (None, "") else None, default=True)

    measure_id = get("measure_id")
    pir = get("post_implementation_review")
    if measure_id not in (None, ""):
        measure_id = str(measure_id).strip()
    else:
        measure_id = None
    if pir not in (None, ""):
        pir = str(pir).strip()
    else:
        pir = None

    if not (
        measure_id
        or measure_status is not None
        or implemented_date is not None
        or pir
        or share
        or anon_raw not in (None, "")
    ):
        return None

    return AdaptationOutcome(
        measure_id=measure_id,
        measure_status=measure_status,
        implemented_date=implemented_date,
        post_implementation_review=pir,
        share_outcome_consented=bool(share),
        anonymise_in_aggregate=True if anon is None else anon,
    )


def _asset_from_mapping(data: dict[str, Any], *, line_label: str) -> UniversalAsset:
    try:
        # Nested adaptation object wins over flat columns.
        nested = data.get("adaptation")
        if isinstance(nested, AdaptationOutcome):
            adaptation = nested
        elif isinstance(nested, dict):
            adaptation = AdaptationOutcome.model_validate(nested)
        else:
            adaptation = _adaptation_from_flat(lambda k: data.get(k))

        asset_id = data.get("asset_id") or data.get("id")
        if not asset_id:
            raise ValueError("asset_id is required")

        return UniversalAsset(
            asset_id=str(asset_id).strip(),
            address=(str(data["address"]).strip() if data.get("address") not in (None, "") else None),
            latitude=_parse_float(data.get("latitude", data.get("lat"))),
            longitude=_parse_float(data.get("longitude", data.get("lon", data.get("lng")))),
            asset_value=_parse_float(data.get("asset_value", data.get("value"))),  # type: ignore[arg-type]
            building_type=str(data.get("building_type") or data.get("building") or "").strip(),
            use_class=str(data.get("use_class") or data.get("use") or "").strip(),
            construction_year=_parse_int(data.get("construction_year", data.get("year_built"))),
            floors=_parse_int(data.get("floors")),
            insurance_coverage=_parse_float(data.get("insurance_coverage", data.get("insured_amount"))),
            existing_adaptation_measures=_parse_measures(
                data.get("existing_adaptation_measures", data.get("adaptation_measures"))
            ),
            ltv=_parse_float(data.get("ltv")),
            loan_id=(str(data["loan_id"]).strip() if data.get("loan_id") not in (None, "") else None),
            adaptation=adaptation,
        )
    except (ValidationError, ValueError, TypeError) as exc:
        raise ValueError(f"{line_label}: {exc}") from exc


def _finalize(
    assets: list[UniversalAsset],
    *,
    valuation_date: date,
    portfolio_id: str | None,
) -> PortfolioUploadRequest:
    if not assets:
        raise ValueError("Portfolio contains no asset rows.")
    if len(assets) > PORTFOLIO_MAX_ASSETS:
        raise ValueError(
            f"Portfolio exceeds maximum of {PORTFOLIO_MAX_ASSETS} assets (got {len(assets)})."
        )
    try:
        return PortfolioUploadRequest(
            valuation_date=valuation_date,
            assets=assets,
            portfolio_id=portfolio_id,
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def parse_portfolio_csv(
    text: str,
    *,
    valuation_date: date,
    portfolio_id: str | None = None,
) -> PortfolioUploadRequest:
    reader = csv.DictReader(io.StringIO(text))
    header_map = _build_header_map(list(reader.fieldnames or []))
    required_present = {"asset_id", "asset_value", "building_type", "use_class"}
    missing = sorted(required_present - set(header_map))
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

    assets: list[UniversalAsset] = []
    for offset, row in enumerate(reader, start=2):
        if not any(str(v).strip() for v in row.values() if v is not None):
            continue
        flat = {canonical: _cell(row, header_map, canonical) for canonical in _COLUMN_ALIASES}
        assets.append(_asset_from_mapping(flat, line_label=f"Row {offset}"))
    return _finalize(assets, valuation_date=valuation_date, portfolio_id=portfolio_id)


def parse_portfolio_csv_bytes(
    data: bytes,
    *,
    valuation_date: date,
    portfolio_id: str | None = None,
) -> PortfolioUploadRequest:
    return parse_portfolio_csv(
        data.decode("utf-8-sig"),
        valuation_date=valuation_date,
        portfolio_id=portfolio_id,
    )


def parse_portfolio_geojson(
    payload: dict[str, Any] | str | bytes,
    *,
    valuation_date: date,
    portfolio_id: str | None = None,
) -> PortfolioUploadRequest:
    """Parse a GeoJSON FeatureCollection (or Feature) into a portfolio.

    Point geometry supplies lat/lon when properties omit them. Properties use the
    same field names as the CSV / JSON asset schema.
    """
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8-sig")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise ValueError("GeoJSON must be an object.")

    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("FeatureCollection.features must be a list.")
    elif kind == "Feature":
        features = [payload]
    else:
        raise ValueError("GeoJSON type must be FeatureCollection or Feature.")

    assets: list[UniversalAsset] = []
    for idx, feature in enumerate(features, start=1):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"Feature {idx}: expected a GeoJSON Feature.")
        props = feature.get("properties") or {}
        if not isinstance(props, dict):
            raise ValueError(f"Feature {idx}: properties must be an object.")
        data = dict(props)
        geometry = feature.get("geometry") or {}
        if (
            isinstance(geometry, dict)
            and geometry.get("type") == "Point"
            and isinstance(geometry.get("coordinates"), (list, tuple))
            and len(geometry["coordinates"]) >= 2
        ):
            lon, lat = geometry["coordinates"][0], geometry["coordinates"][1]
            data.setdefault("longitude", lon)
            data.setdefault("latitude", lat)
            data.setdefault("lon", lon)
            data.setdefault("lat", lat)
        assets.append(_asset_from_mapping(data, line_label=f"Feature {idx}"))

    # Prefer portfolio_id from collection-level property when not passed.
    if portfolio_id is None:
        meta = payload.get("properties") if kind == "FeatureCollection" else None
        if isinstance(meta, dict) and meta.get("portfolio_id"):
            portfolio_id = str(meta["portfolio_id"])

    return _finalize(assets, valuation_date=valuation_date, portfolio_id=portfolio_id)


__all__ = [
    "parse_portfolio_csv",
    "parse_portfolio_csv_bytes",
    "parse_portfolio_geojson",
]
