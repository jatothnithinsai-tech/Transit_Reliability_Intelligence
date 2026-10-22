
-- ====================================================
-- TRANSIT RELIABILITY INTELLIGENCE
-- File: sql/01_create_analytics_views.sql
-- Purpose: Create reusable PostgreSQL analytics views
-- ====================================================

CREATE SCHEMA IF NOT EXISTS analytics;


-- ====================================================
-- VIEW 1: LINE STATUS PER SNAPSHOT
-- One row for each Tube line at each collection time
-- ====================================================

CREATE OR REPLACE VIEW analytics.vw_line_snapshot_status AS
SELECT
    h.line_id,
    l.line_name,
    h.snapshot_time,

    COUNT(*) AS status_records,

    BOOL_OR(
        h.status_severity <> 10
    ) AS was_disrupted,

    BOOL_AND(
        h.status_severity = 10
    ) AS was_good_service

FROM staging.tube_status_history AS h

JOIN staging.tube_lines AS l
    ON h.line_id = l.line_id

GROUP BY
    h.line_id,
    l.line_name,
    h.snapshot_time;


-- ====================================================
-- VIEW 2: LINE RELIABILITY KPIs
-- Percentages describe observed snapshots, not uptime
-- ====================================================

CREATE OR REPLACE VIEW analytics.vw_line_reliability AS
SELECT
    line_id,
    line_name,

    COUNT(*) AS total_snapshots,

    COUNT(*) FILTER (
        WHERE was_disrupted
    ) AS disrupted_snapshots,

    COUNT(*) FILTER (
        WHERE was_good_service
    ) AS good_service_snapshots,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE was_good_service
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS observed_good_service_pct,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE was_disrupted
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS observed_disruption_pct

FROM analytics.vw_line_snapshot_status

GROUP BY
    line_id,
    line_name;


-- ====================================================
-- VIEW 3: DAILY DISRUPTION TRENDS
-- Uses Europe/London local calendar dates
-- ====================================================

CREATE OR REPLACE VIEW analytics.vw_daily_disruption_trends AS
SELECT
    (
        snapshot_time AT TIME ZONE 'Europe/London'
    )::DATE AS observation_date,

    COUNT(DISTINCT snapshot_time)
        AS snapshots_collected,

    COUNT(*) AS total_line_observations,

    COUNT(*) FILTER (
        WHERE was_disrupted
    ) AS disrupted_line_observations,

    COUNT(*) FILTER (
        WHERE was_good_service
    ) AS good_service_observations,

    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE was_disrupted
        ) / NULLIF(COUNT(*), 0),
        2
    ) AS observed_disruption_pct

FROM analytics.vw_line_snapshot_status

GROUP BY
    (
        snapshot_time AT TIME ZONE 'Europe/London'
    )::DATE;


-- ====================================================
-- VERIFICATION
-- ====================================================

SELECT
    line_name,
    total_snapshots,
    observed_good_service_pct,
    observed_disruption_pct
FROM analytics.vw_line_reliability
ORDER BY observed_good_service_pct ASC;

SELECT *
FROM analytics.vw_daily_disruption_trends
ORDER BY observation_date;
