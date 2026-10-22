
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd


# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def get_latest_raw_file():
    """Find the most recent raw TfL snapshot by filename timestamp."""

    raw_files = list(RAW_DIR.glob("tube_status_*.json"))

    if not raw_files:
        raise FileNotFoundError(
            "No raw TfL JSON files found in data/raw"
        )

    return max(raw_files, key=lambda file: file.stem)


def transform_tube_status():
    """Transform raw TfL statuses into structured records."""

    latest_file = get_latest_raw_file()

    timestamp_text = latest_file.stem.replace(
        "tube_status_", ""
    )

    snapshot_time = datetime.strptime(
        timestamp_text,
        "%Y%m%d_%H%M%S"
    ).strftime("%Y-%m-%d %H:%M:%S")

    source_file = latest_file.relative_to(
        PROJECT_ROOT
    ).as_posix()

    with latest_file.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list) or not data:
        raise ValueError(
            "Raw TfL data must be a non-empty list."
        )

    rows = []

    for line in data:
        line_id = line.get("id")
        line_name = line.get("name")
        mode = line.get("modeName")

        statuses = line.get("lineStatuses", [])

        for status in statuses:
            validity_periods = status.get(
                "validityPeriods", []
            )

            from_date = None
            to_date = None
            is_now = None

            if validity_periods:
                period = validity_periods[0]

                from_date = period.get("fromDate")
                to_date = period.get("toDate")
                is_now = period.get("isNow")

            disruption = status.get("disruption") or {}

            rows.append({
                "snapshot_time": snapshot_time,
                "line_id": line_id,
                "line_name": line_name,
                "mode": mode,
                "status_severity": status.get(
                    "statusSeverity"
                ),
                "status_description": status.get(
                    "statusSeverityDescription"
                ),
                "reason": status.get("reason"),
                "disruption_category": disruption.get(
                    "category"
                ),
                "disruption_description": disruption.get(
                    "description"
                ),
                "from_date": from_date,
                "to_date": to_date,
                "is_now": is_now,
                "source_file": source_file
            })

    if not rows:
        raise ValueError(
            "No valid Tube status records were produced."
        )

    df = pd.DataFrame(rows)

    output_file = (
        PROCESSED_DIR / "tube_status_clean.csv"
    )

    temp_file = PROCESSED_DIR / (
        f"tube_status_clean.{os.getpid()}.tmp"
    )

    try:
        with temp_file.open(
            "w", encoding="utf-8", newline=""
        ) as file:
            df.to_csv(file, index=False)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_file, output_file)

    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise

    print(f"Source file: {source_file}")
    print(f"Snapshot time: {snapshot_time}")
    print(f"Clean rows created: {len(df)}")
    print(
        "Processed file saved to: "
        f"{output_file.relative_to(PROJECT_ROOT)}"
    )
    print(f"Columns generated: {len(df.columns)}")
    print()
    print(df.head())


if __name__ == "__main__":
    transform_tube_status()
