-- PathPro system of record on Tiger Data (TimescaleDB + PostGIS). Idempotent.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Road segments (risk units) with geometry.
CREATE TABLE IF NOT EXISTS segments (
    seg_id      integer PRIMARY KEY,
    name        text NOT NULL,
    road_group  text NOT NULL,
    length_m    real NOT NULL,
    geom        geometry(LineString, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS segments_geom_idx ON segments USING gist (geom);

-- Timed crashes snapped to segments (one row per crash-segment assignment).
CREATE TABLE IF NOT EXISTS crashes (
    ts          timestamptz NOT NULL,
    crash_id    text NOT NULL,
    seg_id      integer REFERENCES segments (seg_id),
    weight      real NOT NULL,
    is_ped      boolean NOT NULL,
    severity    char(1),
    light       text,
    surface     text,
    geom        geometry(Point, 4326)
);
SELECT create_hypertable('crashes', by_range('ts', INTERVAL '90 days'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS crashes_seg_ts_idx ON crashes (seg_id, ts DESC);

-- Hourly rollups power crash-history stats and the Risk Tides sparkline.
CREATE MATERIALIZED VIEW IF NOT EXISTS crashes_hourly
WITH (timescaledb.continuous) AS
SELECT time_bucket(INTERVAL '1 hour', ts) AS bucket,
       seg_id,
       sum(weight)                              AS crashes,
       sum(weight) FILTER (WHERE is_ped)        AS ped_crashes,
       sum(weight) FILTER (WHERE light LIKE 'Dark%') AS dark_crashes
FROM crashes
GROUP BY bucket, seg_id
WITH NO DATA;

-- Citywide hour-of-day profile (all segments) for the sparkline.
CREATE OR REPLACE VIEW citywide_hour_profile AS
SELECT extract(hour FROM bucket AT TIME ZONE 'America/New_York')::int AS hour,
       sum(crashes)     AS crashes,
       sum(ped_crashes) AS ped_crashes
FROM crashes_hourly
GROUP BY 1;

-- Precomputed scores per model version (DATA-04: rows = segments x hours x conditions x days).
CREATE TABLE IF NOT EXISTS risk_grid (
    model_version text     NOT NULL,
    seg_id        integer  NOT NULL,
    day_group     text     NOT NULL,
    cond          text     NOT NULL,
    hour          smallint NOT NULL,
    score         smallint NOT NULL,
    PRIMARY KEY (model_version, day_group, cond, hour, seg_id)
);
