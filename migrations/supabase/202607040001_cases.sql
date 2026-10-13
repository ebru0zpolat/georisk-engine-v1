-- GEO-72: case management store (Supabase / PostgreSQL)

CREATE TABLE IF NOT EXISTS cases (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    description       TEXT,
    asset_id          TEXT,
    asset_name        TEXT,
    severity          TEXT NOT NULL,
    priority          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open',
    assigned_to       TEXT,
    tags              JSONB NOT NULL DEFAULT '[]'::jsonb,
    triage_note       TEXT,
    escalation_note   TEXT,
    close_resolution  TEXT,
    z_score           DOUBLE PRECISION,
    anomaly_flag      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS cases_asset_id_idx ON cases (asset_id);
CREATE INDEX IF NOT EXISTS cases_status_idx ON cases (status);

CREATE TABLE IF NOT EXISTS case_transitions (
    id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    case_id       TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    from_status   TEXT,
    to_status     TEXT NOT NULL,
    triggered_by  TEXT NOT NULL DEFAULT 'MANUAL',
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS case_transitions_case_id_idx ON case_transitions (case_id);

COMMENT ON TABLE cases IS 'Risk case records for /v1/cases CRUD (GEO-72).';
COMMENT ON TABLE case_transitions IS 'Immutable case lifecycle audit log (GEO-72).';
