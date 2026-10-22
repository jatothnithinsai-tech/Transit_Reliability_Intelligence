
-- =====================================================
-- TRANSIT RELIABILITY INTELLIGENCE
-- File: sql/views/04_disruption_severity.sql
-- Purpose: Analyze TfL service status distribution
-- =====================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.vw_disruption_severity AS

SELECT
    status_severity,
    status_description,

    COUNT(*) AS total_status_records,

    COUNT(DISTINCT snapshot_time)
        AS snapshots_observed,

    COUNT(DISTINCT line_id)
        AS affected_tube_lines,

    ROUND(
        100.0 * COUNT(*)
        / NULLIF(SUM(COUNT(*)) OVER (), 0),
        2
    ) AS percentage_of_records

FROM staging.tube_status_history

GROUP BY
    status_severity,
    status_description;


-- Verify the saved view

SELECT *
FROM analytics.vw_disruption_severity
ORDER BY
    total_status_records DESC,
    status_severity;
