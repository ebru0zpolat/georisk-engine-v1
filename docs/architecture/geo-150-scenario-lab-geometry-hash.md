# GEO-150 — Spec addendum: `asset_geometry_hash` derivation source

Paste the block below into the **GEO-150** Linear issue description (Scenario Lab / deterministic scenario scoring).

---

## `asset_geometry_hash` (determinism anchor)

**Authoritative source:** `app.geo.geometry_registry` (epic **GEO-188**, issue **GEO-189**).

Downstream modules must **not** compute geometry hashes locally. Import via `app.geo.interfaces` only.

### Derivation algorithm

1. Unwrap GeoJSON `Feature` to `geometry` if present.
2. Recursively round all coordinate values to **6 decimal places** (`_round_coordinates`).
3. Canonical JSON: `json.dumps(geometry, sort_keys=True, separators=(",", ":"))`.
4. `asset_geometry_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()`.

Same geometry → same hash across processes and deployments. Any coordinate change at 6 dp → different hash.

### Required response fields

`ScenarioScoringResult` (and related audit payloads) must include:

| Field | Source |
|-------|--------|
| `asset_geometry_hash` | `GeometryRegistry.hash_for(asset_id)` or `AssetGeometry.asset_geometry_hash` |
| `data_snapshot_id` | From each `RasterTile` used in the scenario (GEO-191); ISO timestamp of underlying raster snapshot |

Missing either field fails acceptance for deterministic replay and audit trails.

### Related issues

- **GEO-188** — Shared geospatial service (parent)
- **GEO-189** — Geometry registry implementation
- **GEO-191** — Raster access (`data_snapshot_id` on `RasterTile`)
- **GEO-192** — `AssetGeometry`, `GeoLookupResult` interface contracts

Repo spec: [geo-188-shared-geospatial-service.md](./geo-188-shared-geospatial-service.md)
