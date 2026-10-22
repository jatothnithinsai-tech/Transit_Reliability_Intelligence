
-- =====================================================
-- TRANSIT RELIABILITY INTELLIGENCE
-- File: sql/views/06_operational_kpi_summary.sql
-- Purpose: Operational KPI summary for Power BI
-- =====================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW
analytics.vw_operational_kpi_summary AS

WITH snapshot_summary AS (
    SELECT
        COUNT(DISTINCT line_id)
            AS tube_lines_monitored,

        COUNT(DISTINCT snapshot_time)
            AS total_snapshots,

        COUNT(*)
            AS total_line_observations,

        COUNT(*) FILTER (
            WHERE was_good_service
        ) AS good_service_observations,

        COUNT(*) FILTER (
            WHERE was_disrupted
        ) AS disrupted_observations,

        MIN(snapshot_time)
            AS first_snapshot_time,

        MAX(snapshot_time)
            AS latest_snapshot_time

    FROM analytics.vw_line_snapshot_status
),

major_summary AS (
    SELECT
        COALESCE(
            SUM(major_status_snapshots), 0
        ) AS major_status_observations,

        COALESCE(
            SUM(planned_closure_snapshots), 0
        ) AS planned_closure_observations

    FROM analytics.vw_major_disruptions_by_line
)

SELECT
    s.tube_lines_monitored,
    s.total_snapshots,
    s.total_line_observations,

    s.good_service_observations,
    s.disrupted_observations,

    ROUND(
        100.0 * s.good_service_observations
        / NULLIF(s.total_line_observations, 0),
        2
    ) AS observed_good_service_pct,

    ROUND(
        100.0 * s.disrupted_observations
        / NULLIF(s.total_line_observations, 0),
        2
    ) AS observed_disruption_pct,

    m.major_status_observations,
    m.planned_closure_observations,

    s.first_snapshot_time,
    s.latest_snapshot_time

FROM snapshot_summary AS s

CROSS JOIN major_summary AS m;


-- Verification
SELECT *
FROM analytics.vw_operational_kpi_summary;
