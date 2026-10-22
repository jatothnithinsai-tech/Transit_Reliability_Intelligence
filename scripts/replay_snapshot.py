"""Explicit optional archival replay; failure returns a nonzero exit code."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.storage.s3_storage import SnapshotStore, StorageConfig, emit


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    try:
        result = SnapshotStore(StorageConfig.from_env()).upload_file(args.snapshot)
        print(f"{'Created' if result.created else 'Verified duplicate'}: {result.key}")
    except Exception as error:
        emit("snapshot_replay_failed", error_type=type(error).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
