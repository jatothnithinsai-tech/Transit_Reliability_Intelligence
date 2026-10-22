"""Read-only PostgreSQL and all loaded source-file lineage verification.

Writes only a sanitized local evidence JSON. Never prints database credentials.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    conn = psycopg2.connect(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT", "5432"),
                            dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
                            password=os.getenv("DB_PASSWORD"), connect_timeout=10)
    conn.set_session(readonly=True, autocommit=False, isolation_level="REPEATABLE READ")
    checks, failures = {}, []
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM analytics.vw_operational_kpi_summary")
            summary = dict(zip([d.name for d in cur.description], cur.fetchone()))
            cur.execute("""SELECT count(*), count(DISTINCT (line_id,snapshot_time)),
                count(*) FILTER (WHERE was_good_service = was_disrupted
                  OR was_good_service IS NULL OR was_disrupted IS NULL)
                FROM analytics.vw_line_snapshot_status""")
            count, distinct_count, invalid = cur.fetchone()
            checks["unique_observation_grain"] = count == distinct_count and invalid == 0
            checks["eleven_lines"] = summary["tube_lines_monitored"] == 11
            checks["complementary_counts"] = (summary["good_service_observations"] +
                summary["disrupted_observations"] == summary["total_line_observations"])
            cur.execute("SELECT sum(total_line_observations), sum(disrupted_line_observations) FROM analytics.vw_daily_disruption_trends")
            daily = cur.fetchone()
            checks["daily_totals_reconcile"] = tuple(daily) == (count, summary["disrupted_observations"])
            cur.execute("""SELECT count(*), count(DISTINCT (snapshot_time,line_id,status_severity,status_description)),
                count(*) FILTER (WHERE source_file IS NULL) FROM staging.tube_status_history""")
            records, unique_records, missing_source = cur.fetchone()
            checks["history_unique_keys"] = records == unique_records
            checks["history_has_lineage"] = missing_source == 0
            cur.execute("SELECT sum(total_status_records) FROM analytics.vw_disruption_severity")
            checks["severity_records_reconcile"] = cur.fetchone()[0] == records
            cur.execute("""SELECT count(*) FROM (SELECT line_id,snapshot_time
                FROM staging.tube_status_history WHERE status_description IN
                ('Severe Delays','Part Closure','Part Suspended','Planned Closure')
                GROUP BY line_id,snapshot_time) s""")
            checks["major_union_reconciles"] = cur.fetchone()[0] == summary["major_status_observations"]
            cur.execute("""SELECT source_file, snapshot_time AT TIME ZONE 'Europe/London',
                line_id,status_severity,status_description,reason
                FROM staging.tube_status_history ORDER BY source_file""")
            groups = {}
            norm = lambda value: value.strip() or None if value is not None else None
            for source, stamp, line, severity, description, reason in cur.fetchall():
                groups.setdefault(source, []).append((stamp, line, severity, description, norm(reason)))
            for source, rows in groups.items():
                path = (ROOT / source).resolve()
                if not path.is_relative_to(ROOT / "data/raw") or not path.is_file():
                    failures.append("Missing or nonlocal raw source")
                    continue
                match = re.fullmatch(r"tube_status_(\d{8}_\d{6})\.json", path.name)
                stamp = datetime.strptime(match[1], "%Y%m%d_%H%M%S")
                data = json.loads(path.read_text(encoding="utf-8"))
                # Loader identity intentionally deduplicates repeated equal statuses.
                expected = {(stamp, line["id"], status["statusSeverity"],
                             status["statusSeverityDescription"], norm(status.get("reason")))
                            for line in data for status in line.get("lineStatuses", [])}
                if Counter(rows) != Counter(expected):
                    failures.append(f"Lineage differs: {path.name}")
            checks["loaded_sources_match_raw"] = not failures
            cur.execute("SELECT status,count(*) FROM monitoring.pipeline_runs GROUP BY status")
            monitoring = dict(cur.fetchall())
            cur.execute("SHOW timezone")
            db_timezone = cur.fetchone()[0]
    finally:
        conn.close()
    raw_sources = {p.relative_to(ROOT).as_posix() for p in (ROOT / "data/raw").glob("*.json")}
    unloaded_sources = sorted(raw_sources - set(groups))
    checks["all_retained_raw_sources_loaded"] = not unloaded_sources
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "read_only": True,
              "passed": all(checks.values()) and not failures, "checks": checks,
              "summary": summary, "history_records": records, "loaded_source_files": len(groups),
              "raw_files_present": len(list((ROOT / "data/raw").glob("*.json"))),
              "unloaded_raw_sources": unloaded_sources,
              "database_timezone": db_timezone, "monitoring_status_counts": monitoring,
              "failures": failures}
    target = ROOT / "docs/validation/local_audit.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, default=str))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
