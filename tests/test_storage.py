"""All SDK calls run under Moto; a socket tripwire forbids external I/O."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError
from moto import mock_aws

from src.storage.s3_storage import (IntegrityError, SnapshotStore, StorageConfig,
                                    StorageError, archive_snapshot_if_enabled,
                                    create_client)

SAMPLE = [{"id": "central", "name": "Central", "modeName": "tube",
           "lineStatuses": [{"statusSeverity": 10,
                             "statusSeverityDescription": "Good Service"}]}]
PAYLOAD = json.dumps(SAMPLE).encode()


def sdk_error(code, status):
    return ClientError({"Error": {"Code": code},
                        "ResponseMetadata": {"HTTPStatusCode": status}}, "PutObject")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SESSION_TOKEN": "testing", "AWS_EC2_METADATA_DISABLED": "true",
            "AWS_DEFAULT_REGION": "us-east-1", "S3_ENABLED": "false"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.moto = mock_aws()
        self.moto.start()
        self.addCleanup(self.moto.stop)
        tripwire = patch("socket.socket.connect", side_effect=AssertionError("Network forbidden"))
        tripwire.start()
        self.addCleanup(tripwire.stop)
        self.client = boto3.client("s3", region_name="us-east-1")
        self.client.create_bucket(Bucket="transit-snapshots-local")
        self.config = StorageConfig(enabled=True)
        self.sleep = Mock()
        self.store = SnapshotStore(self.config, self.client, self.sleep)

    def upload(self, payload=PAYLOAD, source="data/raw/tube_status_20261021_120000.json"):
        return self.store.upload_bytes(payload, source, "2026-10-21T12:00:00")

    def test_success_lineage_checksum_encryption_and_bytes(self):
        result = self.upload()
        response = self.client.get_object(Bucket=self.config.bucket, Key=result.key)
        self.assertTrue(result.created)
        self.assertEqual(response["Body"].read(), PAYLOAD)
        self.assertEqual(response["Metadata"]["sha256"], hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(response["Metadata"]["source-file"], "data/raw/tube_status_20261021_120000.json")
        self.assertEqual(response["ServerSideEncryption"], "AES256")
        self.assertIn("/2026/10/21/", result.key)

    def test_duplicate_is_idempotent(self):
        first = self.upload()
        with patch.object(self.client, "put_object", wraps=self.client.put_object) as put:
            duplicate = self.upload()
        self.assertEqual(first.key, duplicate.key)
        self.assertFalse(duplicate.created)
        put.assert_called_once()
        self.assertEqual(self.client.list_objects_v2(Bucket=self.config.bucket)["KeyCount"], 1)

    def test_changed_bytes_and_different_sources_get_distinct_keys(self):
        first = self.upload()
        changed = self.upload(json.dumps(SAMPLE, indent=2).encode())
        later = self.upload(source="data/raw/tube_status_20261021_130000.json")
        self.assertEqual(len({first.key, changed.key, later.key}), 3)

    def test_invalid_json_and_shape_rejected_before_sdk(self):
        invalid = [b"", b"bad", b"[]", b"{}", b"[null]", b"[NaN]", b"\xff",
                   b"x" * (5 * 1024 * 1024 + 1), json.dumps(SAMPLE * 2).encode()]
        for value in [-1, 21, True, 2.5, None]:
            line = json.loads(PAYLOAD)
            line[0]["lineStatuses"][0]["statusSeverity"] = value
            invalid.append(json.dumps(line).encode())
        with patch.object(self.client, "put_object") as put:
            for payload in invalid:
                with self.subTest(payload=payload[:30]), self.assertRaises(ValueError):
                    self.upload(payload)
        put.assert_not_called()

    def test_absolute_traversal_and_nonportable_lineage_rejected(self):
        for source in ["/secret.json", "../secret.json", "C:/private.json", "a\\b.json", "a\nb.json"]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.upload(source=source)

    def test_file_preserves_raw_bytes_and_filename_timestamp(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tube_status_20261021_134500.json"
            path.write_bytes(PAYLOAD)
            result = self.store.upload_file(path)
        head = self.client.head_object(Bucket=self.config.bucket, Key=result.key)
        self.assertEqual(head["Metadata"]["snapshot-time"], "2026-10-21T13:45:00")
        self.assertEqual(head["Metadata"]["snapshot-timezone"], "Europe/London")

    def test_transient_put_failure_is_retried(self):
        real_put = self.client.put_object
        calls = [sdk_error("SlowDown", 503), None]
        def put(**kwargs):
            error = calls.pop(0)
            if error: raise error
            return real_put(**kwargs)
        with patch.object(self.client, "put_object", side_effect=put) as mocked:
            self.assertTrue(self.upload().created)
        self.assertEqual(mocked.call_count, 2)
        self.sleep.assert_called_once()

    def test_exhausted_network_failure_has_bounded_attempts(self):
        with patch.object(self.client, "put_object", side_effect=EndpointConnectionError(
                endpoint_url="https://private.invalid")) as head:
            with self.assertRaises(StorageError) as error:
                self.upload()
        self.assertEqual(head.call_count, 3)
        self.assertNotIn("private", str(error.exception))

    def test_access_denied_is_not_retried(self):
        with patch.object(self.client, "put_object", side_effect=sdk_error("AccessDenied", 403)) as head:
            with self.assertRaises(StorageError): self.upload()
        self.assertEqual(head.call_count, 1)
        self.sleep.assert_not_called()

    def test_concurrent_conditional_write_verifies_winner(self):
        real_put = self.client.put_object
        def raced_put(**kwargs):
            real_put(**kwargs)
            raise sdk_error("PreconditionFailed", 412)
        with patch.object(self.client, "put_object", side_effect=raced_put):
            self.assertFalse(self.upload().created)

    def test_ambiguous_write_then_retry_is_idempotent(self):
        real_put = self.client.put_object
        calls = 0
        def interrupted(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                real_put(**kwargs)
                raise EndpointConnectionError(endpoint_url="http://localhost")
            return real_put(**kwargs)
        with patch.object(self.client, "put_object", side_effect=interrupted):
            self.assertFalse(self.upload().created)
        self.assertEqual(calls, 2)

    def test_corrupt_bytes_with_matching_metadata_are_rejected(self):
        result = self.upload()
        meta = self.client.head_object(Bucket=self.config.bucket, Key=result.key)["Metadata"]
        self.client.put_object(Bucket=self.config.bucket, Key=result.key, Body=b"corrupt", Metadata=meta)
        with self.assertRaises(IntegrityError): self.upload()

    def test_changed_lineage_is_rejected(self):
        result = self.upload()
        self.client.put_object(Bucket=self.config.bucket, Key=result.key, Body=PAYLOAD,
                               Metadata={"sha256": result.sha256})
        with self.assertRaises(IntegrityError): self.upload()

    def test_disabled_mode_does_not_construct_client_or_read_file(self):
        with patch("src.storage.s3_storage.create_client") as factory:
            self.assertIsNone(archive_snapshot_if_enabled("missing.json"))
        factory.assert_not_called()

    def test_optional_failure_keeps_local_file_and_logs_no_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            path.write_bytes(PAYLOAD)
            with patch.dict(os.environ, {"S3_ENABLED": "true"}), patch(
                    "src.storage.s3_storage.SnapshotStore", side_effect=RuntimeError("secret-value")), self.assertLogs(
                    "transit.storage", level="INFO") as logs:
                self.assertIsNone(archive_snapshot_if_enabled(path))
            self.assertEqual(path.read_bytes(), PAYLOAD)
        self.assertIn("snapshot_archive_failed", "".join(logs.output))
        self.assertNotIn("secret-value", "".join(logs.output))

    def test_remote_endpoint_and_aws_without_opt_in_rejected(self):
        configs = [replace(self.config, endpoint_url="https://s3.amazonaws.com"),
                   replace(self.config, mode="aws"), replace(self.config, mode="invalid"),
                   replace(self.config, endpoint_url="http://user:pass@localhost:5000"),
                   replace(self.config, prefix="../private")]
        for config in configs:
            with self.subTest(config=config), self.assertRaises(StorageError): create_client(config)

    def test_local_client_bypasses_real_credentials(self):
        with patch("boto3.client", return_value=self.client) as factory:
            create_client(self.config)
        self.assertEqual(factory.call_args.kwargs["aws_access_key_id"], "local-testing")
        self.assertEqual(factory.call_args.kwargs["endpoint_url"], "http://127.0.0.1:5000")

    def test_lambda_to_moto_s3_round_trip_and_replay(self):
        from src.cloud import lambda_handler as cloud
        event = {"id": "event-123", "time": "2026-10-21T12:00:00Z"}
        with patch.dict(os.environ, {"S3_ENABLED": "true", "S3_MODE": "local", "TFL_SECRET_ARN": ""}), patch.object(
                cloud, "fetch_snapshot", return_value=SAMPLE), patch(
                "src.storage.s3_storage.create_client", return_value=self.client):
            first = cloud.handler(event, None)
            second = cloud.handler(event, None)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["key"], second["key"])
        stored = self.client.get_object(Bucket=self.config.bucket, Key=first["key"])
        self.assertEqual(json.loads(stored["Body"].read()), SAMPLE)

    def test_optional_failure_reaches_controller_stdout_and_preserves_snapshot(self):
        # Real child process verifies the scheduler/controller capture boundary.
        # The failing store and mocked TfL ensure no external call is possible.
        code = '''
import json, socket, sys
from pathlib import Path
from unittest.mock import patch
from src.ingestion import save_raw_status as ingestion
root = Path(sys.argv[1])
ingestion.PROJECT_ROOT = root
ingestion.RAW_DATA_DIR = root / 'data/raw'
ingestion.RAW_DATA_DIR.mkdir(parents=True)
sample = json.loads(sys.argv[2])
with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')), patch.object(
    ingestion, 'fetch_tfl_data', return_value=sample), patch(
    'src.storage.s3_storage.SnapshotStore', side_effect=RuntimeError('sensitive-error-detail')):
    ingestion.main()
'''
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, S3_ENABLED="true")
            result = subprocess.run([sys.executable, "-c", code, folder, json.dumps(SAMPLE)],
                                    capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"event": "snapshot_archive_failed"', result.stdout)
            self.assertNotIn("sensitive-error-detail", result.stdout + result.stderr)
            snapshots = list((Path(folder) / "data/raw").glob("*.json"))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(json.loads(snapshots[0].read_text()), SAMPLE)
