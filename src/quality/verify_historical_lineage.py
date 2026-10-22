
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

RAW_FILES = [
    "data/raw/tube_status_20261013_115023.json",
    "data/raw/tube_status_20261015_215031.json"
]


def normalize_reason(value):
    if value is None:
        return None

    value = str(value).strip()
    return value if value else None


def get_raw_records(file_path):
    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    records = []

    for line in data:
        for status in line.get("lineStatuses", []):
            records.append((
                line.get("id"),
                status.get("statusSeverity"),
                status.get("statusSeverityDescription"),
                normalize_reason(status.get("reason"))
            ))

    return Counter(records)


def get_database_records(cursor, snapshot_time):
    cursor.execute(
        """
        SELECT
            line_id,
            status_severity,
            status_description,
            reason
        FROM staging.tube_status_history
        WHERE snapshot_time AT TIME ZONE 'Europe/London' = %s
        """,
        (snapshot_time,)
    )

    return Counter(
        (
            line_id,
            severity,
            description,
            normalize_reason(reason)
        )
        for line_id, severity, description, reason
        in cursor.fetchall()
    )


def main():
    connection = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=10
    )

    all_passed = True

    try:
        with connection.cursor() as cursor:
            for filename in RAW_FILES:
                file_path = PROJECT_ROOT / filename

                if not file_path.is_file():
                    raise FileNotFoundError(filename)

                timestamp_text = file_path.stem.replace(
                    "tube_status_", ""
                )

                snapshot_time = datetime.strptime(
                    timestamp_text,
                    "%Y%m%d_%H%M%S"
                )

                raw_records = get_raw_records(file_path)
                db_records = get_database_records(
                    cursor, snapshot_time
                )

                print(f"\nSource: {filename}")
                print(f"Raw records: {raw_records.total()}")
                print(f"Database records: {db_records.total()}")

                if raw_records == db_records:
                    print("PASS - Historical records match")
                else:
                    all_passed = False
                    print("FAIL - Historical records differ")
                    print(
                        "Missing:",
                        list((raw_records - db_records).elements())
                    )
                    print(
                        "Unexpected:",
                        list((db_records - raw_records).elements())
                    )

        if not all_passed:
            raise SystemExit(1)

        print("\nSUCCESS - Historical lineage verification passed")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
