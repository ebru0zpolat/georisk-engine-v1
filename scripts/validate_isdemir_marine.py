"""İsdemir marine-context validation against the live ORAS5 ARCO stores.

Resolves the marine (ocean-surface) context at the İsdemir coastal point
(Payas / İskenderun Bay, Hatay) from the CDS ORAS5 analysis-ready Zarr stores:
nearest-neighbour grid selection, SST + sea-surface-height time series, derived
ocean risk features, and full sha256 checksums.

**Locked declaration (v1):** the real-asset point is ``36.725833, 36.186111``
(not 36.7333, 36.2). The fixture, tests and this script's default are bound to
the exact v1 coordinate; the v1 result is never overwritten after it is seen.
If a different point is ever needed it ships as a separate v2 file.

Every evidence record preserves:
- **selected grid indices** — lat/lon index into each store's coordinate grid
- **selected-cell coordinates** — the grid cell actually selected
- **snap distance** — great-circle distance (km) between the requested point
  and the selected cell
- **request metadata** — location, date window, store URLs, product split,
  variables
- **full checksums** — sha256 over the raw series, the features, and the whole
  record

Usage::

    PYTHONPATH=. python scripts/validate_isdemir_marine.py            # offline stub record
    PYTHONPATH=. python scripts/validate_isdemir_marine.py --live     # live ORAS5 fetch

Credentials are never printed. Live mode requires ``CDSAPI_KEY`` (sent as a
Bearer header) and ``ORAS5_ZARR_URL`` (+ optionally ``ORAS5_ZARR_OPERATIONAL_URL``)
from the environment or ``.env.local``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# When run directly, load the workspace env file BEFORE importing app config so
# pydantic-settings sees the CDS key / ORAS5 URLs from .env.local. Importing this
# module as a library (tests) must NOT touch the process env.
if __name__ == "__main__":
    try:
        from dotenv import load_dotenv

        load_dotenv(_REPO_ROOT / ".env.local")
    except Exception:  # pragma: no cover - python-dotenv is in requirements
        pass

import numpy as np

from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest
from app.core.config import settings

#: İsdemir (Payas / İskenderun Bay) coastal reference point (port: TRIDM) —
#: the locked v1 declaration point. Tests and the pre-declared fixture are
#: bound to this exact coordinate; do not round it.
_DEFAULT_LAT = 36.725833
_DEFAULT_LON = 36.186111
#: WMO 1991–2020 climatological baseline — crosses the 2015 store boundary so
#: both the consolidated and operational stores (and their merge) are exercised.
_DEFAULT_START = date(1991, 1, 1)
_DEFAULT_END = date(2020, 12, 31)

#: ORAS5 regular 0.25° grid (lat -90…90, lon -180…180). Used to pre-declare the
#: expected nearest-neighbour resolution analytically before any live fetch.
_ORAS5_GRID_STEP = 0.25
_ORAS5_LAT_ORIGIN = -90.0
_ORAS5_LON_ORIGIN = -180.0

#: Locked v1 declaration — immutable and held externally (the declaration file
#: is NOT in this repo and is never regenerated here). Its SHA-256 is carried
#: verbatim into every evidence record.
_V1_DECLARATION_SHA256 = (
    "8bc533c23f77067e0c232df20d360bf5c0876c9a9c10555c12f353ad69579579"
)

#: Pre-declared ocean neighbour — observed once live, then locked as a fixture:
#: [507, 864] → (36.75, 36.0), snap 16.8005 km (under the 20 km ocean-snap limit).
_EXPECTED_OCEAN_NEIGHBOUR = {
    "selected_latitude_index": 507,
    "selected_longitude_index": 864,
    "selected_cell": {"latitude": 36.75, "longitude": 36.0},
    "snap_distance_km": 16.8005,
}
#: A live ocean snap beyond this distance is a controlled failure.
_OCEAN_SNAP_LIMIT_KM = 20.0


def _sha256_hex(obj: object) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return float(2 * radius_km * np.arcsin(np.sqrt(a)))


def _series_checksum_payload(series) -> list[float]:
    """Stable checksum payload: values rounded to 6 dp."""
    return [round(float(v), 6) for v in series.tolist()]


def expected_fixture_grid_index(latitude: float, longitude: float) -> dict:
    """Expected (fixture) nearest-neighbour selection on the ORAS5 0.25° grid.

    A fixture expectation from the regular-grid formula — NOT NEMO tripolar
    grid proof. The live record reads the actual indices from the store
    coordinate arrays and stores them as ``verified_live_grid_index``; when they
    differ from this fixture both values are kept and the live index is never
    forced onto the fixture.
    """
    lat_idx = int(round((latitude - _ORAS5_LAT_ORIGIN) / _ORAS5_GRID_STEP))
    lon_idx = int(round((longitude - _ORAS5_LON_ORIGIN) / _ORAS5_GRID_STEP))
    cell_lat = _ORAS5_LAT_ORIGIN + lat_idx * _ORAS5_GRID_STEP
    cell_lon = _ORAS5_LON_ORIGIN + lon_idx * _ORAS5_GRID_STEP
    return {
        "selected_latitude_index": lat_idx,
        "selected_longitude_index": lon_idx,
        "selected_cell": {"latitude": cell_lat, "longitude": cell_lon},
        "snap_distance_km": round(_haversine_km(latitude, longitude, cell_lat, cell_lon), 4),
    }


def _nearest_ocean_cell(
    ds, var: str, latitude: float, longitude: float, *, margin_deg: float = 1.5
) -> tuple[int, int, float, float, float] | None:
    """Nearest non-masked cell to ``(latitude, longitude)`` from the first time step.

    ORAS5 masks land cells with NaN, so a coastal point can snap to a dry cell
    (e.g. İsdemir → cell (36.75, 36.25) has no data). Returns the nearest cell
    with valid values inside a ``margin_deg`` box: ``(lat_idx, lon_idx, lat,
    lon, snap_km)``. Returns ``None`` when the whole window is masked (caller
    falls back to the raw nearest cell).
    """
    lats = np.asarray(ds.latitude.values)
    lons = np.asarray(ds.longitude.values)
    first = ds[var].isel(time=0)
    region = first.sel(
        latitude=slice(latitude - margin_deg, latitude + margin_deg),
        longitude=slice(longitude - margin_deg, longitude + margin_deg),
    )
    valid = ~np.isnan(region.values)
    if not valid.any():
        return None
    idx = np.argwhere(valid)
    rlats = np.asarray(region.latitude.values)
    rlons = np.asarray(region.longitude.values)
    dists = [_haversine_km(latitude, longitude, rlats[i], rlons[j]) for i, j in idx]
    k = int(np.argmin(dists))
    oi, oj = idx[k]
    lat, lon = float(rlats[oi]), float(rlons[oj])
    lat_idx = int(np.abs(lats - lat).argmin())
    lon_idx = int(np.abs(lons - lon).argmin())
    return lat_idx, lon_idx, lat, lon, float(dists[k])


def _series_quality(series, start_date: date | None, end_date: date | None, *, kind: str) -> dict:
    """Homogeneity / scaling / retention / loss checks for one point series."""
    clean = series.dropna()
    expected_months = 0
    if start_date and end_date:
        expected_months = (
            (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
        )
    retention = (
        round(len(clean) / expected_months, 4) if expected_months else round(float(len(clean) > 0), 4)
    )

    diffs = clean.diff().dropna()
    std = clean.std()
    if std and not np.isnan(std):
        jumps = diffs[diffs.abs() > 3 * std]
    else:
        jumps = diffs[diffs.abs() > 0]

    if clean.empty:
        sane: bool | None = None
    elif kind == "sst":
        sane = bool(clean.min() >= -10 and clean.max() <= 350)  # °C or K magnitudes
    else:
        sane = bool(clean.min() >= -10 and clean.max() <= 10)  # metres

    return {
        "expected_months": expected_months,
        "available": int(len(clean)),
        "retention": retention,
        "loss_pathway": "missing_months_dropped; empty series yields zero features",
        "homogeneity": {
            "max_jump": round(float(diffs.abs().max()), 6) if not diffs.empty else 0.0,
            "jump_count_gt_3sigma": int(len(jumps)),
        },
        "scaling": {"unit_range_sane": sane},
    }


def build_record(
    *,
    live: bool,
    payload: Oras5PointRequest,
    generated_at: datetime,
) -> dict:
    connector = CDSOras5Connector()
    record: dict = {
        "schema_version": "1.0",
        "validation_id": f"ISD-MARINE-{generated_at:%Y%m%d-%H%M%S}",
        "case_id": "isdemir_marine_context",
        "subject": "İsdemir (Payas / İskenderun Bay) marine context — ORAS5",
        "mode": "live" if live else "offline",
        "georisk_version": settings.georisk_version,
        "generated_at": generated_at.isoformat(),
        "request": {
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "start_date": str(payload.start_date) if payload.start_date else None,
            "end_date": str(payload.end_date) if payload.end_date else None,
            "data_access": "cds-arco-zarr",
            "auth": "bearer-header",
        },
    }

    record["declaration"] = {
        "id": "isdemir-v1",
        "point": {"latitude": _DEFAULT_LAT, "longitude": _DEFAULT_LON},
        "sha256": _V1_DECLARATION_SHA256,
        "note": "immutable v1 declaration (external file, not in repo); sha256 carried verbatim",
    }
    if not live:
        features = connector._fallback_features()
        record["expected_fixture_grid_index"] = expected_fixture_grid_index(
            payload.latitude, payload.longitude
        )
        record["expected_fixture_ocean_neighbour"] = dict(_EXPECTED_OCEAN_NEIGHBOUR)
        record["verified_live_grid_index"] = None
        record["verified_live_ocean_neighbour"] = None
        record["live_fixture_match"] = None
        record["run_status"] = "offline_stub"
        record["gate_failures"] = []
        record["series"] = None
        record["features"] = features
        record["ocean_risk_score"] = connector.ocean_risk_score_from_features(features)
        record["evidence_classification"] = _evidence_classification()
        record["checksums"] = {
            "features_sha256": _sha256_hex(features),
            "record_sha256": "",
        }
        record["checksums"]["record_sha256"] = _sha256_hex(record)
        return record

    missing = []
    if not settings.oras5_zarr_url:
        missing.append("ORAS5_ZARR_URL")
    if not settings.copernicus_cds_api_key:
        missing.append("CDSAPI_KEY")
    if missing:
        raise SystemExit(
            f"Live mode missing env (env or .env.local): {', '.join(missing)}; "
            "run without --live for the offline stub record."
        )

    sst_var, sea_level_var = connector._resolve_vars()
    store_urls = connector._store_urls_for(payload.start_date, payload.end_date)
    fixture = expected_fixture_grid_index(payload.latitude, payload.longitude)
    record["expected_fixture_grid_index"] = fixture
    record["expected_fixture_ocean_neighbour"] = dict(_EXPECTED_OCEAN_NEIGHBOUR)
    record["request"]["store_urls"] = store_urls
    record["request"]["variables"] = [sst_var, sea_level_var]
    record["request"]["product_types"] = connector._cdsapi_product_types_for(
        payload.start_date, payload.end_date
    )

    grid_selection: dict[str, dict] = {}
    ocean_selection: dict[str, dict] = {}
    sst_parts: list = []
    sea_level_parts: list = []
    for url in store_urls:
        ds = connector._open_dataset(url)
        lats = np.asarray(ds.latitude.values)
        lons = np.asarray(ds.longitude.values)
        lat_idx = int(np.abs(lats - payload.latitude).argmin())
        lon_idx = int(np.abs(lons - payload.longitude).argmin())
        cell_lat = float(lats[lat_idx])
        cell_lon = float(lons[lon_idx])
        grid_selection[url] = {
            "selected_latitude_index": lat_idx,
            "selected_longitude_index": lon_idx,
            "selected_cell": {"latitude": cell_lat, "longitude": cell_lon},
            "snap_distance_km": round(
                _haversine_km(payload.latitude, payload.longitude, cell_lat, cell_lon),
                4,
            ),
        }
        # Marine context comes from the nearest non-masked (ocean) cell; a
        # coastal point can otherwise snap to a dry land cell with no data.
        ocean = _nearest_ocean_cell(ds, sst_var, payload.latitude, payload.longitude)
        if ocean is not None:
            o_lat_idx, o_lon_idx, o_lat, o_lon, o_snap = ocean
            ocean_selection[url] = {
                "selected_latitude_index": o_lat_idx,
                "selected_longitude_index": o_lon_idx,
                "selected_cell": {"latitude": o_lat, "longitude": o_lon},
                "snap_distance_km": round(o_snap, 4),
                "basis": "nearest non-masked cell at first time step",
            }
            series_lat, series_lon = o_lat, o_lon
        else:
            ocean_selection[url] = dict(grid_selection[url])
            ocean_selection[url]["basis"] = "fully masked window — raw nearest cell"
            series_lat, series_lon = cell_lat, cell_lon
        series_payload = Oras5PointRequest(
            latitude=series_lat,
            longitude=series_lon,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        sst_parts.append(connector._point_series_from_store(url, sst_var, series_payload))
        sea_level_parts.append(connector._point_series_from_store(url, sea_level_var, series_payload))

    sst = connector._concat_series(sst_parts)
    sea_level = connector._concat_series(sea_level_parts)
    features = connector._features_from_series(sst, sea_level)

    def _series_summary(series, *, kind: str) -> dict:
        clean = series.dropna()
        return {
            "count": int(len(clean)),
            "first": str(clean.index.min()) if not clean.empty else None,
            "last": str(clean.index.max()) if not clean.empty else None,
            "min": round(float(clean.min()), 6) if not clean.empty else None,
            "max": round(float(clean.max()), 6) if not clean.empty else None,
            "quality": _series_quality(
                clean, payload.start_date, payload.end_date, kind=kind
            ),
            "sha256": _sha256_hex(_series_checksum_payload(clean)),
        }

    record["verified_live_grid_index"] = grid_selection
    record["verified_live_ocean_neighbour"] = ocean_selection
    fixture_idx = (fixture["selected_latitude_index"], fixture["selected_longitude_index"])
    ocean_fixture_idx = (
        _EXPECTED_OCEAN_NEIGHBOUR["selected_latitude_index"],
        _EXPECTED_OCEAN_NEIGHBOUR["selected_longitude_index"],
    )
    live_grid_match = all(
        (sel["selected_latitude_index"], sel["selected_longitude_index"]) == fixture_idx
        for sel in grid_selection.values()
    )
    live_ocean_match = all(
        (sel["selected_latitude_index"], sel["selected_longitude_index"]) == ocean_fixture_idx
        and abs(sel["snap_distance_km"] - _EXPECTED_OCEAN_NEIGHBOUR["snap_distance_km"]) < 0.01
        for sel in ocean_selection.values()
    )
    ocean_snap_max = max(
        (sel["snap_distance_km"] for sel in ocean_selection.values()), default=0.0
    )
    # live_fixture_match is a comparison result ONLY — the verified live values
    # are authoritative and never overwrite the expected_fixture_* values.
    record["live_fixture_match"] = {
        "grid_index": live_grid_match,
        "ocean_neighbour": live_ocean_match,
        "ocean_snap_max_km": ocean_snap_max,
        "ocean_snap_limit_km": _OCEAN_SNAP_LIMIT_KM,
        "note": "comparison result only; verified_live_* is authoritative and never overwrites expected_fixture_*",
    }
    # Controlled fail: mismatch or ocean snap > limit → run_status=failed with
    # the observed values preserved, production_eligible stays false, and the
    # failure is recorded as an open gate record.
    gate_failures: list[str] = []
    if not live_grid_match:
        gate_failures.append("verified_live_grid_index != expected_fixture_grid_index")
    if not live_ocean_match:
        gate_failures.append("verified_live_ocean_neighbour != expected_fixture_ocean_neighbour")
    if ocean_snap_max > _OCEAN_SNAP_LIMIT_KM:
        gate_failures.append(
            f"ocean snap {ocean_snap_max:.4f} km exceeds the {_OCEAN_SNAP_LIMIT_KM} km limit"
        )
    record["run_status"] = "passed" if not gate_failures else "failed"
    record["gate_failures"] = gate_failures
    record["request"]["series_basis"] = (
        "nearest non-masked ocean cell per store (mask from first time step); "
        "raw nearest cell when the window is fully masked"
    )
    record["series"] = {
        "sst": _series_summary(sst, kind="sst"),
        "sea_surface_height": _series_summary(sea_level, kind="ssh"),
        "rounding_note": "series values rounded to 6 decimal places for stable checksums",
    }
    record["features"] = features
    record["ocean_risk_score"] = connector.ocean_risk_score_from_features(features)
    record["evidence_classification"] = _evidence_classification()
    record["operational_evidence"] = {
        "authenticated_arco_data_access": "passed",
        "provisional_cross_product_series": "1991–2020 consolidated+operational merged series",
        "note": (
            "this record is operational evidence (authenticated Zarr metadata+data "
            "access); it does NOT close homogeneity / scaling-calibration / "
            "retention / asset-loss gates (see docs/validation/oras5-evidence-gates.md); "
            "ERA5 smoke is recorded separately by scripts/era5_retrieve_smoke.py"
        ),
    }
    record["checksums"] = {
        "series_sha256": _sha256_hex(
            {
                "sst": _series_checksum_payload(sst.dropna()),
                "sea_surface_height": _series_checksum_payload(sea_level.dropna()),
            }
        ),
        "features_sha256": _sha256_hex(features),
        "record_sha256": "",
    }
    record["checksums"]["record_sha256"] = _sha256_hex(record)
    return record


def _evidence_classification() -> dict:
    """Canonical evidence-gate statuses (docs/validation/oras5-evidence-gates.md).

    Immutable classification: the declaration and fixture-coordinate gates pass;
    offline/implementation evidence passes; live, scientific-calibration,
    production, retention and loss-pathway gates stay pending / not established;
    production_eligible is False until the remaining gates close. A successful
    live run adds operational evidence but does not flip these statuses.
    """
    return {
        "real_asset_declaration": "passed",
        "fixture_coordinate_selection": "passed",
        "offline_pipeline_parity": "passed",
        "deterministic_fixture_selection": "passed",
        "credential_contract": "passed",
        "dimensionality_controls": "passed",
        "fail_closed_behavior": "passed",
        "actual_oras5_grid_selection": "pending",
        "live_source_parity": "pending",
        "cross_product_homogeneity": "pending",
        "scaling_calibration": "pending",
        "production_smoke": "pending",
        "durable_retention": "pending",
        "asset_loss_pathway": "not_established",
        "production_eligible": False,
    }


def _summary_markdown(record: dict) -> str:
    mode_badge = "🟢 LIVE" if record["mode"] == "live" else "⚪ OFFLINE STUB"
    lines = [
        f"# GeoRisk Validation Evidence — İsdemir marine context (ORAS5) {mode_badge}",
        "",
        f"- **Validation id:** `{record['validation_id']}`",
        f"- **GeoRisk version:** {record['georisk_version']}",
        f"- **Schema version:** {record['schema_version']}",
        f"- **Generated at:** {record['generated_at']}",
        "",
    ]
    req = record["request"]
    lines += [
        "## Request metadata",
        "",
        f"- **Point:** {req['latitude']}, {req['longitude']} (İsdemir / Payas, İskenderun Bay)",
        f"- **Window:** {req['start_date']} → {req['end_date']}",
        f"- **Data access:** {req['data_access']} ({req['auth']})",
        f"- **Variables:** {', '.join(req.get('variables', []))}",
        f"- **Product types:** {', '.join(req.get('product_types', []))}",
        f"- **Stores:** {', '.join(req.get('store_urls', []))}",
        "",
    ]
    decl = record.get("declaration", {})
    if decl:
        lines.append(
            f"- **Declaration v1 sha256:** `{decl['sha256']}` (point {decl['point']['latitude']}, "
            f"{decl['point']['longitude']}; carried verbatim, file untouched)"
        )
        lines.append("")
    lines.append(
        f"- **Expected fixture grid index:** "
        f"{json.dumps(record.get('expected_fixture_grid_index'))}"
    )
    lines.append(
        f"- **Expected fixture ocean neighbour:** "
        f"{json.dumps(record.get('expected_fixture_ocean_neighbour'))}"
    )
    lines.append("")
    if record["verified_live_grid_index"]:
        lines.append("## Verified live grid index (read from store arrays)")
        lines.append("")
        for url, sel in record["verified_live_grid_index"].items():
            lines.append(
                f"- `{url}` → indices ({sel['selected_latitude_index']}, "
                f"{sel['selected_longitude_index']}), cell "
                f"({sel['selected_cell']['latitude']}, {sel['selected_cell']['longitude']}), "
                f"snap {sel['snap_distance_km']} km"
            )
        lines.append("")
    if record.get("verified_live_ocean_neighbour"):
        lines.append("## Verified live ocean neighbour (nearest non-masked cell)")
        lines.append("")
        for url, sel in record["verified_live_ocean_neighbour"].items():
            lines.append(
                f"- `{url}` → indices ({sel['selected_latitude_index']}, "
                f"{sel['selected_longitude_index']}), cell "
                f"({sel['selected_cell']['latitude']}, {sel['selected_cell']['longitude']}), "
                f"snap {sel['snap_distance_km']} km · {sel.get('basis', '')}"
            )
        lines.append("")
    if record.get("live_fixture_match"):
        match = record["live_fixture_match"]
        lines.append("## Live–fixture match (comparison result only)")
        lines.append("")
        lines.append(
            f"- **run_status:** `{record.get('run_status')}` · grid_index `{match['grid_index']}` · "
            f"ocean_neighbour `{match['ocean_neighbour']}` · ocean snap "
            f"{match['ocean_snap_max_km']} km ≤ {match['ocean_snap_limit_km']} km"
        )
        lines.append(f"- **gate_failures:** {record.get('gate_failures') or 'none'}")
        lines.append(f"- **note:** {match['note']}")
        lines.append("")
    if record["series"]:
        lines.append("## Time series")
        lines.append("")
        for name, summary in record["series"].items():
            if name == "rounding_note":
                continue
            lines.append(
                f"- **{name}:** n={summary['count']} {summary['first']} → {summary['last']} "
                f"({summary['min']} … {summary['max']}) · sha256 `{summary['sha256']}`"
            )
        lines.append("")
    lines.append("## Features and checksums")
    lines.append("")
    lines.append(f"- **Features:** {json.dumps(record['features'])}")
    lines.append(f"- **Ocean risk score:** {record['ocean_risk_score']}/100")
    for key, digest in record["checksums"].items():
        lines.append(f"- **{key}:** `{digest}`")
    lines.append("")
    if record.get("evidence_classification"):
        lines.append("## Evidence classification (canonical gate statuses)")
        lines.append("")
        for key, value in record["evidence_classification"].items():
            lines.append(f"- **{key}:** `{value}`")
        lines.append("")
    if record.get("gate_failures"):
        lines.append("## Open gate failures (controlled fail)")
        lines.append("")
        for failure in record["gate_failures"]:
            lines.append(f"- ❌ {failure}")
        lines.append("")
        lines.append(
            "- Observed values preserved in `verified_live_*`; `production_eligible=false`; "
            "record written for the audit trail."
        )
        lines.append("")
    if record.get("operational_evidence"):
        lines.append("## Operational evidence")
        lines.append("")
        for key, value in record["operational_evidence"].items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")
    return "\n".join(lines)


def main() -> list[Path]:
    parser = argparse.ArgumentParser(description="İsdemir marine-context validation (ORAS5).")
    parser.add_argument("--live", action="store_true", help="Fetch from the live ORAS5 stores.")
    parser.add_argument("--lat", type=float, default=_DEFAULT_LAT, help="Request latitude.")
    parser.add_argument("--lon", type=float, default=_DEFAULT_LON, help="Request longitude.")
    parser.add_argument("--start-date", type=date.fromisoformat, default=_DEFAULT_START)
    parser.add_argument("--end-date", type=date.fromisoformat, default=_DEFAULT_END)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "validation",
        help=(
            "Where to write the evidence JSON + Markdown "
            "(default data/validation — NOT data/evidence, which the Erdemir "
            "ValidationService consumes)."
        ),
    )
    parser.add_argument(
        "--generated-at",
        type=datetime.fromisoformat,
        default=None,
        help="ISO-8601 timestamp (default: now UTC).",
    )
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(timezone.utc)
    payload = Oras5PointRequest(
        latitude=args.lat,
        longitude=args.lon,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    record = build_record(live=args.live, payload=payload, generated_at=generated_at)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"isdemir_marine_{generated_at:%Y%m%d-%H%M%S}_evidence"
    json_path = args.out_dir / f"{stem}.json"
    md_path = args.out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_summary_markdown(record), encoding="utf-8")

    mode = "live" if args.live else "offline"
    print(f"[isdemir-marine] mode={mode} point=({args.lat}, {args.lon}) "
          f"window={args.start_date}→{args.end_date}")
    print(f"[isdemir-marine] ocean_risk_score={record['ocean_risk_score']}/100 "
          f"features={json.dumps(record['features'])}")
    if record["verified_live_grid_index"]:
        for url, sel in record["verified_live_grid_index"].items():
            print(f"[isdemir-marine] snap {url.split('/')[-1]} → "
                  f"indices=({sel['selected_latitude_index']}, {sel['selected_longitude_index']}) "
                  f"cell=({sel['selected_cell']['latitude']}, {sel['selected_cell']['longitude']}) "
                  f"snap_km={sel['snap_distance_km']}")
    for url, sel in (record.get("verified_live_ocean_neighbour") or {}).items():
        print(f"[isdemir-marine] ocean {url.split('/')[-1]} → "
              f"indices=({sel['selected_latitude_index']}, {sel['selected_longitude_index']}) "
              f"cell=({sel['selected_cell']['latitude']}, {sel['selected_cell']['longitude']}) "
              f"snap_km={sel['snap_distance_km']} ({sel.get('basis', '')})")
    print(f"[isdemir-marine] checksums record_sha256={record['checksums']['record_sha256']}")
    print(f"[isdemir-marine] wrote {json_path.resolve()}")
    print(f"[isdemir-marine] wrote {md_path.resolve()}")
    if record.get("run_status") == "failed":
        print(
            f"[isdemir-marine] CONTROLLED FAIL run_status=failed "
            f"gate_failures={record.get('gate_failures')} "
            f"(observed preserved; production_eligible=false; open gate failure record)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return [json_path, md_path]


if __name__ == "__main__":
    main()
