PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    retrieved_at TEXT,
    source_year INTEGER,
    source_version TEXT NOT NULL DEFAULT '',
    UNIQUE(name, url, source_year, source_version)
);
CREATE TABLE IF NOT EXISTS calendar_versions (
    year INTEGER PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('sample','authoritative','partial')),
    source_id INTEGER REFERENCES sources(id),
    imported_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saints (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    alternate_names TEXT NOT NULL DEFAULT '[]',
    category TEXT NOT NULL DEFAULT 'Saint',
    rank TEXT NOT NULL DEFAULT '',
    service_rank TEXT NOT NULL DEFAULT 'NONE',
    source_rank_text TEXT NOT NULL DEFAULT '',
    source_order INTEGER NOT NULL DEFAULT 0,
    source_primary INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    source_id INTEGER REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS saint_commemorations (
    saint_id INTEGER NOT NULL REFERENCES saints(id) ON DELETE CASCADE,
    civil_date TEXT NOT NULL,
    PRIMARY KEY(saint_id, civil_date)
);
CREATE TABLE IF NOT EXISTS feasts (
    id INTEGER PRIMARY KEY,
    civil_date TEXT NOT NULL,
    name TEXT NOT NULL,
    rank TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    liturgical_status TEXT NOT NULL DEFAULT '',
    service_rank TEXT NOT NULL DEFAULT 'NONE',
    source_rank_text TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    source_id INTEGER REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS fasting_records (
    id INTEGER PRIMARY KEY,
    civil_date TEXT NOT NULL,
    level TEXT NOT NULL,
    period TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'en',
    source_id INTEGER REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS source_day_metadata (
    id INTEGER PRIMARY KEY,
    civil_date TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    liturgical_week TEXT NOT NULL DEFAULT '',
    tone INTEGER,
    source_url TEXT NOT NULL DEFAULT '',
    service_rank TEXT NOT NULL DEFAULT 'NO_DATA',
    rank_name_en TEXT NOT NULL DEFAULT '',
    rank_name_ru TEXT NOT NULL DEFAULT '',
    rank_source_text TEXT NOT NULL DEFAULT '',
    rank_source_name TEXT NOT NULL DEFAULT '',
    rank_source_url TEXT NOT NULL DEFAULT '',
    rank_status TEXT NOT NULL DEFAULT 'no_data',
    source_id INTEGER REFERENCES sources(id),
    UNIQUE(civil_date, language, source_id)
);
CREATE TABLE IF NOT EXISTS public_holidays (
    id INTEGER PRIMARY KEY,
    civil_date TEXT NOT NULL,
    name TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    source_id INTEGER REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS user_overrides (
    id INTEGER PRIMARY KEY,
    civil_date TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    action TEXT NOT NULL,
    value_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY,
    civil_date TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    primary_json TEXT NOT NULL,
    secondary_json TEXT NOT NULL,
    resolution_json TEXT,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS sync_metadata (
    source_name TEXT PRIMARY KEY,
    last_attempt TEXT,
    last_success TEXT,
    status TEXT NOT NULL DEFAULT 'Never synchronized',
    message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_saint_date ON saint_commemorations(civil_date);
CREATE INDEX IF NOT EXISTS idx_saint_name ON saints(display_name);
CREATE INDEX IF NOT EXISTS idx_feast_date ON feasts(civil_date);
CREATE INDEX IF NOT EXISTS idx_source_day_date ON source_day_metadata(civil_date);
