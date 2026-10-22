"""Cloud execution behavior with Moto and intercepted HTTP; no real AWS calls."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import unittest
from unittest.mock import Mock, patch

import boto3
from botocore.exceptions import ClientError
from moto import mock_aws
import requests
import responses

from src.cloud import lambda_handler as cloud
from src.cloud.execution_registry import ExecutionInProgress, ExecutionRegistry
from src.ingestion.tfl_client import API_URL, BoundedRetry
from src.storage.s3_storage import SnapshotStore, StorageConfig, StorageError
from test_storage import SAMPLE


EVENT = {"scheduled_time": "2026-10-22T00:00:00Z", "execution_id": "attempt-1",
         "schedule_arn": "arn:aws:scheduler:eu-west-2:000000000000:schedule/transit/hourly",
         "attempt_number": "1"}


class CloudHttpTests(unittest.TestCase):
    @responses.activate
    def test_successful_api_payload(self):
        responses.get(API_URL, json=SAMPLE)
        self.assertEqual(cloud.fetch_snapshot(), SAMPLE)

    @responses.activate
    def test_503_then_success_uses_http_retry(self):
        responses.get(API_URL, status=503)
        responses.get(API_URL, json=SAMPLE)
        self.assertEqual(cloud.fetch_snapshot(), SAMPLE)
        self.assertEqual(len(responses.calls), 2)

    @responses.activate
    def test_exhausted_server_failures_propagate(self):
        responses.get(API_URL, status=503)
        with self.assertRaises(requests.RequestException): cloud.fetch_snapshot()
        self.assertEqual(len(responses.calls), 4)

    def test_timeout_configuration_and_propagation(self):
        with patch('requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            session.get.side_effect = requests.Timeout("sensitive-url")
            with self.assertRaises(requests.Timeout): cloud.fetch_snapshot()
        self.assertEqual(session.get.call_args.kwargs['timeout'], (3, 10))
        retry = session.mount.call_args.args[1].max_retries
        self.assertEqual((retry.connect, retry.read, retry.total), (3, 3, 3))

    def test_retry_after_is_bounded(self):
        response = Mock(headers={"Retry-After": "900"})
        self.assertEqual(BoundedRetry(total=3).get_retry_after(response), 5)

    @responses.activate
    def test_invalid_api_payloads_never_become_snapshots(self):
        for payload in [{"error": "bad"}, [], [{"id": "central"}], [None]]:
            responses.get(API_URL, json=payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError): cloud.fetch_snapshot()
            responses.reset()


class ScheduledExecutionTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SESSION_TOKEN": "testing", "AWS_EC2_METADATA_DISABLED": "true", "S3_ENABLED": "true",
            "S3_MODE": "local", "TFL_SECRET_ARN": "", "EXPECTED_SCHEDULE_ARN": EVENT["schedule_arn"]})
        env.start(); self.addCleanup(env.stop)
        moto = mock_aws(); moto.start(); self.addCleanup(moto.stop)
        guard = patch("socket.socket.connect", side_effect=AssertionError("External network forbidden"))
        guard.start(); self.addCleanup(guard.stop)
        self.client = boto3.client("s3", region_name="us-east-1")
        self.client.create_bucket(Bucket="transit-snapshots-local")
        factory = patch("src.storage.s3_storage.create_client", return_value=self.client)
        factory.start(); self.addCleanup(factory.stop)
        self.store = SnapshotStore(StorageConfig(enabled=True), self.client, sleep=lambda _: None)

    def invoke(self, event=None):
        return cloud.handler(event or EVENT, Mock(aws_request_id="request-123"))

    def test_success_preserves_capture_and_schedule_lineage(self):
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE): result = self.invoke()
        response = self.client.get_object(Bucket=self.store.config.bucket, Key=result["key"])
        payload = response["Body"].read()
        self.assertEqual(json.loads(payload), SAMPLE)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), result["sha256"])
        self.assertEqual(response["Metadata"]["snapshot-time"], result["snapshot_time"])
        self.assertEqual(response["Metadata"]["source-file"], result["source_file"])
        self.assertEqual(result["scheduled_time"], "2026-10-22T00:00:00+00:00")
        self.assertIn("attempt-1", result["key"])

    def test_retry_attempt_id_change_does_not_refetch_or_upload(self):
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE) as fetch:
            first = self.invoke()
            second = self.invoke({**EVENT, "execution_id": "attempt-2", "attempt_number": "2"})
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(first["key"], second["key"])
        self.assertFalse(second["created"])
        self.assertEqual(self.client.list_objects_v2(Bucket=self.store.config.bucket, Prefix="raw/")["KeyCount"], 1)

    def test_distinct_hour_gets_a_distinct_snapshot(self):
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE):
            first = self.invoke()
            second = self.invoke({**EVENT, "scheduled_time": "2026-10-22T01:00:00Z", "execution_id": "attempt-3"})
        self.assertNotEqual(first["key"], second["key"])

    def test_invalid_event_is_rejected_before_api_or_s3(self):
        cases = [None, {}, {**EVENT, "scheduled_time": "2026-10-22T00:00:00"},
                 {**EVENT, "schedule_arn": "wrong"}, {**EVENT, "execution_id": "../unsafe"}]
        with patch.object(cloud, "fetch_snapshot") as fetch, patch.object(cloud, "SnapshotStore") as store:
            for value in cases:
                with self.subTest(value=value), self.assertRaises(RuntimeError): cloud.handler(value, None)
        fetch.assert_not_called(); store.assert_not_called()

    def test_failed_fetch_is_sanitized_and_can_be_retried(self):
        with patch.object(cloud, "fetch_snapshot", side_effect=requests.Timeout("app_key=secret-test")), self.assertLogs(
                "transit.storage", level="INFO") as logs:
            with self.assertRaises(RuntimeError) as error: self.invoke()
        self.assertNotIn("secret-test", str(error.exception) + "".join(logs.output))
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE): self.assertTrue(self.invoke()["created"])

    def test_invalid_data_creates_no_raw_object(self):
        with patch.object(cloud, "fetch_snapshot", return_value={"error": "bad"}):
            with self.assertRaises(RuntimeError): self.invoke()
        self.assertEqual(self.client.list_objects_v2(Bucket=self.store.config.bucket, Prefix="raw/")["KeyCount"], 0)

    def test_s3_upload_denied_marks_failure(self):
        real_put = self.client.put_object
        def put(**kwargs):
            if kwargs["Key"].startswith("raw/"):
                raise ClientError({"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}}, "PutObject")
            return real_put(**kwargs)
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE), patch.object(self.client, "put_object", side_effect=put):
            with self.assertRaises(RuntimeError): self.invoke()
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE): self.assertTrue(self.invoke()["created"])

    def test_active_lease_blocks_a_concurrent_owner(self):
        registry = ExecutionRegistry(self.store)
        scheduled, _, identity = cloud.parse_event(EVENT)
        registry.claim(identity, scheduled, "owner-one")
        with self.assertRaises(ExecutionInProgress): registry.claim(identity, scheduled, "owner-two")

    def test_expired_lease_recovers_a_timed_out_invocation(self):
        stamp = datetime(2026, 10, 22, tzinfo=timezone.utc)
        registry = ExecutionRegistry(self.store, now=lambda: stamp)
        scheduled, _, identity = cloud.parse_event(EVENT)
        first, _ = registry.claim(identity, scheduled, "old-owner")
        recovered = ExecutionRegistry(self.store, now=lambda: stamp + timedelta(seconds=151))
        second, _ = recovered.claim(identity, scheduled, "new-owner")
        self.assertNotEqual(first.etag, second.etag)
        with self.assertRaises(StorageError): registry.finish(first, {"key": "stale"})

    def test_duplicate_detects_corruption_without_refetch(self):
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE): result = self.invoke()
        self.client.put_object(Bucket=self.store.config.bucket, Key=result["key"], Body=b"corrupt")
        with patch.object(cloud, "fetch_snapshot") as fetch:
            with self.assertRaises(RuntimeError): self.invoke()
        fetch.assert_not_called()

    def test_verified_download_rejects_wrong_expected_hash(self):
        with patch.object(cloud, "fetch_snapshot", return_value=SAMPLE): result = self.invoke()
        with self.assertRaises(StorageError): self.store.read_snapshot(result["key"], "0" * 64)

    def test_secret_is_read_only_after_claim_and_never_in_raw_data(self):
        with patch.dict(os.environ, {"TFL_SECRET_ARN": "mock-secret"}), patch.object(
                cloud, "read_api_key", return_value="sensitive-key") as secret, patch.object(
                cloud, "fetch_snapshot", return_value=SAMPLE) as fetch:
            first = self.invoke()
            self.invoke({**EVENT, "execution_id": "attempt-2"})
        secret.assert_called_once_with("mock-secret")
        fetch.assert_called_once_with("sensitive-key")
        data, _ = self.store.read_snapshot(first["key"])
        self.assertNotIn(b"sensitive-key", data)
