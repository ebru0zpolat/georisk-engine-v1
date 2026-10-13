-- GEO-190: spatial index schema (PostGIS / Supabase)
-- Requires PostGIS extension and existing assets(id) table.

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE assets
    ADD COLUMN IF NOT EXISTS geometry geometry(Geometry, 4326);

CREATE INDEX IF NOT EXISTS assets_geometry_gist
    ON assets USING GIST (geometry);

CREATE TABLE IF NOT EXISTS coastlines (
    zone_id   TEXT PRIMARY KEY,
    geom      geometry(MultiLineString, 4326) NOT NULL,
    source    TEXT NOT NULL DEFAULT 'naturalearth_10m',
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS coastlines_geom_gist
    ON coastlines USING GIST (geom);

COMMENT ON TABLE coastlines IS
    'Preloaded coastline segments for coastal_zone() and distance_to_coast() (GEO-190).';

COMMENT ON COLUMN assets.geometry IS
    'Asset footprint in WGS84; synced from asset_geometries GeoJSON where polygonal.';
