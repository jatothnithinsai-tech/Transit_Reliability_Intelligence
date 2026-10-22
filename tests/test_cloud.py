import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.cloud import lambda_handler as cloud
from src.ingestion import save_raw_status as ingestion
from src.storage.s3_storage import StorageError, UploadResult
from test_storage import SAMPLE


class CloudEntryPointTests(unittest.TestCase):
    def test_disabled_lambda_has_no_network_or_secret_access(self):
        with patch.dict(os.environ, {"S3_ENABLED": "false"}), patch.object(
                cloud, "fetch_snapshot") as fetch, patch.object(cloud, "read_api_key") as secret:
            with self.assertRaises(StorageError): cloud.handler({}, None)
        fetch.assert_not_called()
        secret.assert_not_called()

    def test_lambda_uploads_stable_event_lineage(self):
        store = Mock()
        store.upload_bytes.return_value = UploadResult("raw/key.json", "abc", True)
        registry = Mock()
        registry.claim.return_value = (Mock(), None)
        class FixedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"S3_ENABLED": "true", "S3_MODE": "local", "TFL_SECRET_ARN": ""}), patch.object(
                cloud, "fetch_snapshot", return_value=SAMPLE), patch.object(cloud, "SnapshotStore", return_value=store), patch.object(
                cloud, "ExecutionRegistry", return_value=registry), patch.object(cloud, "datetime", FixedClock):
            response = cloud.handler({"id": "event-123", "time": "2026-10-21T12:00:00Z"}, None)
        self.assertTrue(response["created"])
        args = store.upload_bytes.call_args.args
        self.assertRegex(args[1], r"^lambda/tube_status_20261021_120000_000000_[0-9a-f]{16}_event-123\.json$")
        self.assertEqual(args[2], "2026-10-21T12:00:00+00:00")

    def test_lambda_failures_are_sanitized_and_propagate(self):
        with patch.dict(os.environ, {"S3_ENABLED": "true", "S3_MODE": "local", "TFL_SECRET_ARN": ""}), patch.object(
                cloud, "fetch_snapshot", side_effect=RuntimeError("app_key=secret-value")), self.assertLogs(
                "transit.storage", level="INFO") as logs:
            with self.assertRaises(RuntimeError) as error: cloud.handler({}, None)
        self.assertNotIn("secret-value", str(error.exception) + "".join(logs.output))

    def test_ingestion_http_failure_does_not_disclose_api_key(self):
        with patch.object(ingestion, "fetch_tfl_data", side_effect=ingestion.requests.HTTPError(
                "https://api.tfl.gov.uk/?app_key=secret-value")):
            with self.assertRaises(RuntimeError) as error: ingestion.main()
        self.assertNotIn("secret-value", str(error.exception))
