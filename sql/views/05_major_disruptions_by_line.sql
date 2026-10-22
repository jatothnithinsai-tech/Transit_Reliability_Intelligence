
-- =====================================================
-- TRANSIT RELIABILITY INTELLIGENCE
-- File: sql/views/05_major_disruptions_by_line.sql
-- Purpose: Analyze major service statuses by Tube line
-- =====================================================

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW
analytics.vw_major_disruptions_by_line AS

WITH line_snapshot_flags AS (
    SELECT
        line_id,
        snapshot_time,

        BOOL_OR(
            status_description = 'Severe Delays'
        ) AS has_severe_delays,

        BOOL_OR(
            status_description IN (
                'Part Closure',
                'Part Suspended'
            )
        ) AS has_closure_or_suspension,

        BOOL_OR(
            status_description = 'Planned Closure'
        ) AS has_planned_closure

    FROM staging.tube_status_history

    GROUP BY
        line_id,
        snapshot_time
)

SELECT
    l.line_id,
    l.line_name,

    COUNT(*) AS snapshots_observed,

    COUNT(*) FILTER (
        WHERE s.has_severe_delays
    ) AS severe_delay_snapshots,

    COUNT(*) FILTER (
        WHERE s.has_closure_or_suspension
    ) AS closure_or_suspension_snapshots,

    COUNT(*) FILTER (
        WHERE s.has_planned_closure
    ) AS planned_closure_snapshots,

    COUNT(*) FILTER (
        WHERE
            s.has_severe_delays
            OR s.has_closure_or_suspension
            OR s.has_planned_closure
    ) AS major_status_snapshots

FROM line_snapshot_flags AS s

JOIN staging.tube_lines AS l
    ON s.line_id = l.line_id

GROUP BY
    l.line_id,
    l.line_name;


-- Verify the view

SELECT
    line_name,
    snapshots_observed,
    severe_delay_snapshots,
    closure_or_suspension_snapshots,
    planned_closure_snapshots,
    major_status_snapshots
FROM analytics.vw_major_disruptions_by_line
ORDER BY
    major_status_snapshots DESC,
    line_name;
