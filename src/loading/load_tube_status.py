
import csv
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


# Project configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

CSV_FILE = (
    PROJECT_ROOT / "data" / "processed" / "tube_status_clean.csv"
)

REQUIRED_COLUMNS = [
    "snapshot_time",
    "line_id",
    "line_name",
    "status_severity",
    "status_description",
    "source_file"
]


def optional(value):
    if value is None:
        return None

    value = str(value).strip()
    return value if value else None


def parse_boolean(value):
    value = optional(value)

    if value is None:
        return None

    if value.lower() in ("true", "1"):
        return True

    if value.lower() in ("false", "0"):
        return False

    raise ValueError(f"Invalid boolean value: {value}")


def read_processed_data():
    if not CSV_FILE.is_file():
        raise FileNotFoundError(
            f"Processed CSV not found: {CSV_FILE}"
        )

    with CSV_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        fieldnames = reader.fieldnames or []

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in fieldnames
        ]

        if missing:
            raise ValueError(
                f"Missing CSV columns: {missing}"
            )

        rows = list(reader)

    if not rows:
        raise ValueError("Processed CSV contains no records.")

    source_files = set()

    for row in rows:
        for column in REQUIRED_COLUMNS:
            if optional(row.get(column)) is None:
                raise ValueError(
                    f"Missing required value: {column}"
                )

        severity = int(row["status_severity"])

        if not 0 <= severity <= 20:
            raise ValueError(
                f"Invalid severity: {severity}"
            )

        parse_boolean(row.get("is_now"))

        source_file = row["source_file"]
        source_files.add(source_file)

        raw_path = PROJECT_ROOT / source_file

        if not raw_path.is_file():
            raise FileNotFoundError(
                f"Original raw file missing: {raw_path}"
            )

    if len(source_files) != 1:
        raise ValueError(
            "CSV must contain exactly one raw snapshot source."
        )

    return rows


def connect_database():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=10
    )


def load_tube_status():
    rows = read_processed_data()

    connection = connect_database()

    inserted_count = 0
    lineage_updated_count = 0

    try:
        with connection:
            with connection.cursor() as cursor:

                for row in rows:
                    # Maintain Tube line reference data
                    cursor.execute(
                        """
                        INSERT INTO staging.tube_lines (
                            line_id,
                            line_name,
                            created_at,
                            updated_at
                        )
                        VALUES (%s, %s, NOW(), NOW())

                        ON CONFLICT (line_id)
                        DO UPDATE SET
                            line_name = EXCLUDED.line_name,
                            updated_at = NOW()

                        WHERE staging.tube_lines.line_name
                            IS DISTINCT FROM EXCLUDED.line_name
                        """,
                        (
                            row["line_id"],
                            row["line_name"]
                        )
                    )

                    # Insert new historical status records
                    cursor.execute(
                        """
                        INSERT INTO staging.tube_status_history (
                            snapshot_time,
                            line_id,
                            status_severity,
                            status_description,
                            reason,
                            disruption_from,
                            disruption_to,
                            is_now,
                            source_file,
                            loaded_at
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, NOW()
                        )

                        ON CONFLICT (
                            snapshot_time,
                            line_id,
                            status_severity,
                            status_description
                        )
                        DO NOTHING
                        """,
                        (
                            row["snapshot_time"],
                            row["line_id"],
                            int(row["status_severity"]),
                            row["status_description"],
                            optional(row.get("reason")),
                            optional(row.get("from_date")),
                            optional(row.get("to_date")),
                            parse_boolean(row.get("is_now")),
                            row["source_file"]
                        )
                    )

                    inserted_count += cursor.rowcount

                    # Correct lineage on previously loaded records
                    cursor.execute(
                        """
                        UPDATE staging.tube_status_history
                        SET source_file = %s
                        WHERE snapshot_time = %s
                          AND line_id = %s
                          AND status_severity = %s
                          AND status_description = %s
                          AND source_file IS DISTINCT FROM %s
                        """,
                        (
                            row["source_file"],
                            row["snapshot_time"],
                            row["line_id"],
                            int(row["status_severity"]),
                            row["status_description"],
                            row["source_file"]
                        )
                    )

                    lineage_updated_count += cursor.rowcount

        print("PostgreSQL load completed successfully!")
        print(f"CSV records processed: {len(rows)}")
        print(f"New history records inserted: {inserted_count}")
        print(
            "Existing lineage records updated: "
            f"{lineage_updated_count}"
        )
        print(
            f"Original source file: {rows[0]['source_file']}"
        )

    except Exception:
        print(
            "Database load failed. "
            "Transaction rolled back."
        )
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    load_tube_status()
