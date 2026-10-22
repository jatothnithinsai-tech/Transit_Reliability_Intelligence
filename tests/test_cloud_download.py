import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import download_cloud_snapshot as download
from test_storage import PAYLOAD


class CloudDownloadTests(unittest.TestCase):
    def test_same_file_can_be_replayed_without_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.json"
            download.write_without_overwrite(path, PAYLOAD)
            before = path.stat().st_mtime_ns
            download.write_without_overwrite(path, PAYLOAD)
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_conflicting_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.json"
            path.write_bytes(b"existing")
            with self.assertRaises(FileExistsError): download.write_without_overwrite(path, PAYLOAD)
            self.assertEqual(path.read_bytes(), b"existing")

    def test_download_isolated_from_local_raw_and_processed_data(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Mock()
            store.read_snapshot.return_value = (PAYLOAD, {"sha256": hashlib.sha256(PAYLOAD).hexdigest()})
            with patch.object(download, "ROOT", Path(folder)), patch.object(download, "SnapshotStore", return_value=store), patch(
                    "sys.argv", ["download", "--key", "raw/tfl/tube/sample.json"]):
                download.main()
            inbox = Path(folder) / "data/cloud_inbox"
            self.assertEqual(len(list(inbox.glob("*.lineage.json"))), 1)
            self.assertFalse((Path(folder) / "data/raw").exists())
            self.assertFalse((Path(folder) / "data/processed").exists())

    def test_disabled_storage_performs_no_download(self):
        with patch.dict(os.environ, {"S3_ENABLED": "false"}), patch("sys.argv", ["download", "--key", "raw/sample.json"]), patch(
                "src.storage.s3_storage.create_client") as factory:
            with self.assertRaises(SystemExit) as result: download.main()
        self.assertEqual(result.exception.code, 1)
        factory.assert_not_called()
