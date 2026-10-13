-- GEO-189: canonical asset geometry store (Supabase / PostgreSQL)
-- Requires an existing assets(id) table (TEXT primary key).

CREATE TABLE IF NOT EXISTS asset_geometries (
    asset_id      TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    geojson       JSONB NOT NULL,
    geometry_hash TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS asset_geometries_geometry_hash_idx
    ON asset_geometries (geometry_hash);

COMMENT ON TABLE asset_geometries IS
    'Canonical verified GeoJSON per asset; geometry_hash is SHA-256 of rounded canonical geometry (GEO-189).';

COMMENT ON COLUMN asset_geometries.geometry_hash IS
    'asset_geometry_hash — derived by app.geo.interfaces.derive_geometry_hash';
