# GEO-188 — Shared Geospatial Data Service (Epic)

**Parent of:** GEO-189, GEO-190, GEO-191, GEO-192  
**Blocks:** GEO-6, GEO-7, GEO-8, GEO-150, GEO-172  
**Status:** Spec (Linear sync pending)

---

## Goal

Create a shared geospatial data service so spatial queries, verified geometry handling, and raster access are implemented once and reused across risk modules.

## Problem

Asset locations are currently handled ad hoc, with coordinates embedded in asset records and elevation looked up on demand. This creates duplication and weakens the architecture:

- **GEO-8** and **GEO-7** both need spatial queries, but there is no shared spatial index or geo lookup service.
- **GEO-172** needs raster-backed hazard inputs, including DEM and ERA5-based access patterns, which would require the same geospatial plumbing.
- **GEO-150** depends on `asset_geometry_hash` as a determinism anchor, but the current architecture does not define a verified geometry registry as the source of that hash.

## Proposed scope

1. Add a **spatial index** and geo lookup layer for asset and hazard queries.
2. Add a **geometry registry** for canonical, verified asset geometries and derived hashes.
3. Add **raster tile access** primitives for elevation and climate/hazard layers.
4. Define **shared interfaces** so downstream scoring modules reuse the same geospatial foundation.

## Intended consumers

| Issue | Need |
|-------|------|
| GEO-6 | Sea-level baseline model — coastal zones, tide-gauge context |
| GEO-7 | Z-score anomaly detection for sea-level rise |
| GEO-8 | Coastal exposure scoring (elevation + proximity) |
| GEO-150 | Scenario Lab — `asset_geometry_hash` determinism anchor |
| GEO-172 | Flood and heat risk models (DEM, ERA5) |

---

## Architecture

```text
app/geo/
├── __init__.py
├── geometry_registry.py      # canonical GeoJSON store + SHA-256 hash derivation
├── spatial_index.py          # PostGIS + shapely queries
├── raster_access.py          # MERIT DEM, ERA5, Sentinel-5P, PSMSL
└── interfaces.py             # shared contracts only — all external imports go here
```

**Enforcement:** No file outside `app/geo/` may import `geometry_registry`, `spatial_index`, or `raster_access` directly. All external access goes through `app.geo.interfaces` (CI import test or lint).

## Downstream integration

| Consumer | Needs from `app/geo/` |
|----------|------------------------|
| GEO-6 | `spatial_index.coastal_zone()`, `raster_access.sea_level_anomaly()` |
| GEO-7 | `spatial_index.coastal_zone()`, `raster_access.sea_level_anomaly()` |
| GEO-8 | `spatial_index.distance_to_coast()`, `spatial_index.elevation_band()` |
| GEO-150 | `geometry_registry.hash_for()` → `asset_geometry_hash` |
| GEO-172 | `raster_access.elevation_at()`, `raster_access.era5_temperature()` |

---

## Child issues

| ID | Title | Blocks | Blocked by |
|----|-------|--------|------------|
| GEO-189 | Geometry Registry + `asset_geometry_hash` | GEO-150 | — |
| GEO-190 | Spatial Index (PostGIS + shapely) | GEO-7, GEO-8 | — |
| GEO-191 | Raster Access Layer | GEO-8, GEO-172 | — |
| GEO-192 | Shared interfaces + integration tests | — | GEO-189, GEO-190, GEO-191 |

Detailed acceptance criteria: see sections below and `docs/architecture/issues/geo-189.md` … `geo-192.md`.

---

## GEO-189 — Geometry Registry + `asset_geometry_hash`

**Priority:** P1 · High  
**Parent:** GEO-188 · **Blocks:** GEO-150

### Goal

Build the canonical geometry store and the sole authoritative source for `asset_geometry_hash`.

### Hash derivation (deterministic across processes)

```python
import json
import hashlib


def derive_geometry_hash(geojson: dict) -> str:
    geometry = geojson.get("geometry", geojson)  # unwrap Feature if needed
    geometry = _round_coordinates(geometry, precision=6)
    canonical = json.dumps(geometry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

`_round_coordinates` must recurse into nested arrays (Polygon, MultiPolygon).

### DB migration (Supabase)

```sql
CREATE TABLE asset_geometries (
    asset_id      TEXT PRIMARY KEY REFERENCES assets(id),
    geojson       JSONB NOT NULL,
    geometry_hash TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Every `register()` / `update()` call writes an audit log entry:

```json
{ "event": "geometry_registered", "asset_id", "asset_geometry_hash", "version", "timestamp" }
```

### Acceptance criteria

- Hash stable on repeated calls for same geometry.
- Hash differs on any coordinate change at 6 decimal places.
- `update()` increments `version`.
- `GeometryNotFoundError` never returns `None`.
- Migration clean on Supabase dev.

---

## GEO-190 — Spatial Index (PostGIS + shapely)

**Priority:** P1 · High  
**Parent:** GEO-188 · **Blocks:** GEO-7, GEO-8

### Goal

Efficient spatial queries over registered asset geometries and hazard zones.

### API surface

```python
class SpatialIndex:
    def assets_within(self, polygon: dict) -> list[str]: ...
    def distance_to_coast(self, asset_id: str) -> float:  # km
    def elevation_band(self, asset_id: str) -> ElevationBand:
        # BAND_0_2M | BAND_2_5M | BAND_5_10M | ABOVE_10M
    def coastal_zone(self, asset_id: str) -> str:
        # Named zone for sea level baseline lookup (GEO-6)
```

### PostGIS schema

```sql
ALTER TABLE assets ADD COLUMN geometry geometry(Polygon, 4326);
CREATE INDEX assets_geometry_gist ON assets USING GIST(geometry);
```

- **Coastline source:** NaturalEarth 10m or OSM coastline (preloaded into PostGIS as `coastlines` table).
- `elevation_band()` calls `RasterAccess.elevation_at()` internally — no direct raster access from this layer.
- Shapely + rtree used for in-process test queries (no Supabase dependency in unit tests).

### Acceptance criteria

- `distance_to_coast()` and `elevation_band()` correct for 3 golden fixtures (coastal low, coastal high, inland).
- `assets_within()` returns correct subset for a test polygon.
- `coastal_zone()` returns deterministic string for known coordinates.

---

## GEO-191 — Raster Access Layer

**Priority:** P1 · High  
**Parent:** GEO-188 · **Blocks:** GEO-8, GEO-172

### Goal

Unified access layer for elevation and climate raster sources. Consumers never import underlying clients directly.

### API surface

```python
class RasterAccess:
    def elevation_at(self, lat: float, lon: float) -> RasterTile:
        # Source: MERIT DEM or Copernicus DEM 30m
    def no2_column(self, lat: float, lon: float, date: str) -> RasterTile:
        # Source: Sentinel-5P via Copernicus CDS API
    def era5_temperature(self, lat: float, lon: float, date: str) -> RasterTile:
        # Source: ERA5 via Copernicus CDS API
    def sea_level_anomaly(self, coastal_zone: str, date: str) -> RasterTile:
        # Source: PSMSL bulk + NOAA CO-OPS
```

`RasterTile.data_snapshot_id` is an ISO timestamp of the underlying data snapshot. This field must propagate through every scoring result that uses raster inputs, satisfying GEO-150's requirement that `data_snapshot_id` is mandatory in responses.

### Data sources (all free)

| Method | Source | Auth |
|--------|--------|------|
| `elevation_at` | MERIT DEM / Copernicus DEM 30m | None (HTTP tile) |
| `no2_column` | Sentinel-5P, Copernicus | CDS API key (`COPERNICUS_CDS_API_KEY`) |
| `era5_temperature` | ERA5, Copernicus CDS | CDS API key |
| `sea_level_anomaly` | PSMSL + NOAA CO-OPS | None (bulk CSV) |

Missing CDS key raises `RasterSourceConfigError`, not a silent fallback.

### Acceptance criteria

- `elevation_at()` within ±5 m of SRTM reference for 3 test coords.
- `era5_temperature()` returns plausible value for known location/date.
- `data_snapshot_id` populated on every `RasterTile`.
- `RasterSourceConfigError` raised (not swallowed) on missing API key.
- All sources mockable in unit tests without network calls.

---

## GEO-192 — Shared interfaces + integration tests

**Priority:** P1 · High  
**Parent:** GEO-188 · **Blocked by:** GEO-189, GEO-190, GEO-191

### Goal

Define typed contracts all downstream modules import from, and validate the four layers work together end-to-end.

### `app/geo/interfaces.py` exports

```python
@dataclass
class AssetGeometry:
    asset_id: str
    geojson: dict
    asset_geometry_hash: str    # SHA-256, authoritative for GEO-150
    registered_at: datetime
    version: int


class ElevationBand(Enum):
    BAND_0_2M  = "0-2m"
    BAND_2_5M  = "2-5m"
    BAND_5_10M = "5-10m"
    ABOVE_10M  = ">10m"


@dataclass
class RasterTile:
    source: str                 # "MERIT_DEM" | "SENTINEL5P" | "ERA5" | "PSMSL"
    lat: float
    lon: float
    value: float
    unit: str
    data_snapshot_id: str       # ISO timestamp — propagates to ScenarioScoringResult


@dataclass
class GeoLookupResult:
    asset_id: str
    distance_to_coast_km: float
    elevation_band: ElevationBand
    coastal_zone: str
    asset_geometry_hash: str
```

### Integration test scenarios

1. Register geometry → derive hash → pass to scenario_scoring mock → verify `asset_geometry_hash` in response matches.
2. Register coastal asset → `distance_to_coast()` + `elevation_band()` → `GeoLookupResult` fields populated correctly.
3. `raster_access.elevation_at()` → `elevation_band()` classification → coastal_exposure_score derivation (GEO-8 flow).
4. Full chain: asset registered → `GeoLookupResult` → `sea_level_anomaly()` → Z-score input (GEO-7 flow).

### Acceptance criteria

- All four interfaces importable from `app.geo.interfaces` with no circular imports.
- No file outside `app/geo/` imports concrete modules (enforced by CI).
- All 4 integration scenarios pass.
- `mypy --strict` clean on `app/geo/`.

---

## GEO-150 cross-reference (determinism anchor)

When updating **GEO-150** (Scenario Lab), add to its description:

> **`asset_geometry_hash` source:** Derived exclusively by `app.geo.geometry_registry.derive_geometry_hash()` (see GEO-189). Canonical JSON serialization: geometry only (Feature unwrapped), coordinates rounded to 6 dp, `json.dumps(..., sort_keys=True, separators=(",", ":"))`, SHA-256 hex digest. Scenario scoring must include this hash and every raster-backed `data_snapshot_id` from `RasterTile` in `ScenarioScoringResult` for reproducibility.

See [geo-150-scenario-lab-geometry-hash.md](./geo-150-scenario-lab-geometry-hash.md) for paste-ready Linear text.
