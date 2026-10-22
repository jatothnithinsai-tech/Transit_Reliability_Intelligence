"""Read-only validation of the local PostgreSQL views used by the dashboard."""
import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
QUERIES = {
    "columns": """SELECT table_name, column_name, data_type FROM information_schema.columns
        WHERE table_schema = 'analytics' ORDER BY table_name, ordinal_position""",
    "summary": "SELECT * FROM analytics.vw_operational_kpi_summary",
    "line_keys": """SELECT COUNT(*) AS rows, COUNT(DISTINCT line_id) AS distinct_keys,
        COUNT(*) FILTER (WHERE line_id IS NULL OR line_name IS NULL) AS null_keys
        FROM analytics.vw_line_reliability""",
    "snapshot_grain": """SELECT COUNT(*) AS rows,
        COUNT(DISTINCT (line_id, snapshot_time)) AS distinct_line_snapshots,
        COUNT(DISTINCT snapshot_time) AS distinct_collection_times,
        COUNT(*) FILTER (WHERE was_disrupted IS NULL OR was_good_service IS NULL) AS null_flags,
        COUNT(*) FILTER (WHERE was_disrupted = was_good_service) AS non_complementary_flags
        FROM analytics.vw_line_snapshot_status""",
    "line_reliability": "SELECT * FROM analytics.vw_line_reliability ORDER BY line_name",
    "daily": "SELECT * FROM analytics.vw_daily_disruption_trends ORDER BY observation_date",
    "severity": "SELECT * FROM analytics.vw_disruption_severity ORDER BY total_status_records DESC, status_severity",
    "major": "SELECT * FROM analytics.vw_major_disruptions_by_line ORDER BY line_name",
    "major_keys": """SELECT COUNT(*) AS rows, COUNT(DISTINCT line_id) AS distinct_keys,
        COUNT(*) FILTER (WHERE line_id IS NULL) AS null_keys
        FROM analytics.vw_major_disruptions_by_line""",
    "view_definitions": """SELECT viewname, definition FROM pg_views WHERE schemaname = 'analytics'
        ORDER BY viewname""",
}


def main():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "transit_reliability_intelligence"),
        user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD"),
        connect_timeout=10,
    )
    conn.set_session(readonly=True, autocommit=True)
    result = {}
    try:
        with conn.cursor() as cur:
            for label, sql in QUERIES.items():
                cur.execute(sql)
                names = [d.name for d in cur.description]
                result[label] = [dict(zip(names, row)) for row in cur.fetchall()]
    finally:
        conn.close()
    target = ROOT / "powerbi" / "validation" / "database_audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, default=str, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["line_keys", "snapshot_grain", "major_keys", "summary"]}, default=str))


if __name__ == "__main__":
    main()
