"""Download one verified S3 snapshot to an ignored inbox; never loads PostgreSQL."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from src.storage.s3_storage import SnapshotStore, StorageConfig


def write_without_overwrite(path, payload):
    if path.exists():
        if path.read_bytes() != payload:
            raise FileExistsError("A different file already exists; no overwrite allowed")
        return
    # Exclusive creation preserves existing artifacts even under concurrent runs.
    with path.open("xb") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True)
    parser.add_argument("--sha256", help="Optional expected digest from the completed execution manifest")
    args = parser.parse_args()
    try:
        store = SnapshotStore(StorageConfig.from_env())
        payload, metadata = store.read_snapshot(args.key, args.sha256)
        digest = hashlib.sha256(payload).hexdigest()
        inbox = ROOT / "data/cloud_inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        # Identical bytes at different collection times still need distinct
        # source lineage sidecars.
        identity = hashlib.sha256(args.key.encode("utf-8")).hexdigest()[:16]
        stem = f"{identity}-{digest}"
        target = inbox / f"{stem}.json"
        write_without_overwrite(target, payload)
        lineage = json.dumps({"s3_key": args.key, "metadata": metadata}, indent=2).encode("utf-8")
        write_without_overwrite(inbox / f"{stem}.lineage.json", lineage)
        print(f"Verified snapshot saved to {target.relative_to(ROOT)}")
    except Exception as error:
        print(f"Cloud download failed: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
