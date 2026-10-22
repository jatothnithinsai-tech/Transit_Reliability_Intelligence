
import os
import json
import logging
import requests
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv


# Project configuration
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.ingestion.tfl_client import fetch_tube_status
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("TFL_API_KEY")

API_URL = "https://api.tfl.gov.uk/Line/Mode/tube/Status"

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_tfl_data():
    """Fetch TfL data with timeout and automatic retries."""
    return fetch_tube_status(API_KEY)


def save_raw_data(data):
    """Save raw JSON atomically to prevent partial files."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_file = RAW_DATA_DIR / f"tube_status_{timestamp}.json"

    temp_file = RAW_DATA_DIR / (
        f"tube_status_{timestamp}.{os.getpid()}.tmp"
    )

    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_file, output_file)

    except Exception:
        if temp_file.exists():
            temp_file.unlink()

        raise

    return output_file


def main():
    try:
        data = fetch_tfl_data()
    except requests.RequestException as error:
        # Requests errors can include the app_key query parameter in their URL.
        raise RuntimeError(f"TfL request failed: {type(error).__name__}") from None

    output_file = save_raw_data(data)

    # Mirror only after the durable local write. Direct script execution needs
    # the project root on sys.path; the existing scheduler command stays valid.
    if os.getenv("S3_ENABLED", "false").lower() == "true":
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.storage.s3_storage import archive_snapshot_if_enabled
        # The controller captures stdout on successful stages, including a
        # successful local write whose optional mirror failed.
        logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
        archive_snapshot_if_enabled(output_file)

    print(
        f"Raw TfL data saved to: "
        f"{output_file.relative_to(PROJECT_ROOT)}"
    )

    print(f"Tube line objects received: {len(data)}")


if __name__ == "__main__":
    main()
