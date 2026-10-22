"""Immutable, content-addressed TfL snapshots with bounded retries.

No client is constructed until storage is explicitly enabled. Local mode never
uses the AWS credential chain. AWS mode requires a second explicit opt-in.
"""
import base64
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

LOGGER = logging.getLogger("transit.storage")
MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024


class StorageError(RuntimeError):
    """A sanitized storage failure; raw SDK messages may contain endpoints."""


class IntegrityError(StorageError):
    """Stored bytes or lineage do not match the immutable snapshot."""


def emit(event, **fields):
    LOGGER.info(json.dumps({"event": event, **fields}, sort_keys=True))


@dataclass(frozen=True)
class StorageConfig:
    enabled: bool = False
    bucket: str = "transit-snapshots-local"
    prefix: str = "raw/tfl/tube"
    region: str = "eu-west-2"
    mode: str = "local"
    endpoint_url: str = "http://127.0.0.1:5000"
    allow_aws: bool = False
    attempts: int = 3

    @classmethod
    def from_env(cls):
        # Ignore unused storage settings when disabled, including invalid ones.
        if os.getenv("S3_ENABLED", "false").lower() != "true":
            return cls()
        return cls(
            enabled=True,
            bucket=os.getenv("S3_BUCKET", cls.bucket),
            prefix=os.getenv("S3_PREFIX", cls.prefix),
            region=os.getenv("AWS_REGION", cls.region),
            mode=os.getenv("S3_MODE", "local"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL", cls.endpoint_url),
            allow_aws=os.getenv("S3_ALLOW_AWS", "false").lower() == "true",
        )

    def validate(self):
        if not self.enabled:
            raise StorageError("Storage is disabled")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", self.bucket):
            raise StorageError("Invalid bucket name")
        if not re.fullmatch(r"[a-z0-9][a-z0-9/_-]*", self.prefix) or "//" in self.prefix:
            raise StorageError("Invalid object prefix")
        if self.prefix.endswith("/") or not 1 <= self.attempts <= 5:
            raise StorageError("Invalid storage configuration")
        if self.mode == "local":
            endpoint = urlsplit(self.endpoint_url)
            if (endpoint.scheme not in {"http", "https"}
                    or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or endpoint.username or endpoint.password or endpoint.query
                    or endpoint.fragment or endpoint.path not in {"", "/"}):
                raise StorageError("Local storage requires a loopback endpoint")
        elif self.mode != "aws" or not self.allow_aws:
            raise StorageError("AWS storage requires explicit S3_ALLOW_AWS=true")


def create_client(config):
    config.validate()
    import boto3
    from botocore.config import Config
    # Manual retry below is the sole retry loop, including post-write reads.
    sdk_config = Config(connect_timeout=3, read_timeout=10,
                        retries={"total_max_attempts": 1},
                        s3={"addressing_style": "path"})
    kwargs = {"region_name": config.region, "config": sdk_config}
    if config.mode == "local":
        kwargs.update(endpoint_url=config.endpoint_url,
                      aws_access_key_id="local-testing",
                      aws_secret_access_key="local-testing",
                      config=sdk_config.merge(Config(proxies={})))
    return boto3.client("s3", **kwargs)


def validate_snapshot(payload):
    if not payload or len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Snapshot must contain 1 byte to 5 MiB")
    def invalid_constant(_):
        raise ValueError("Non-finite JSON values are not allowed")
    try:
        data = json.loads(payload.decode("utf-8"), parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Snapshot must be UTF-8 JSON") from error
    if not isinstance(data, list) or not data:
        raise ValueError("Snapshot must be a non-empty list of Tube lines")
    ids = set()
    for line in data:
        if not isinstance(line, dict) or not all(
                isinstance(line.get(k), str) and line[k].strip()
                for k in ("id", "name", "modeName")):
            raise ValueError("Each line needs id, name and modeName")
        if line["modeName"] != "tube" or line["id"] in ids:
            raise ValueError("Duplicate line or non-Tube mode")
        ids.add(line["id"])
        statuses = line.get("lineStatuses")
        if not isinstance(statuses, list) or not statuses:
            raise ValueError("Every line requires service statuses")
        for status in statuses:
            if not isinstance(status, dict):
                raise ValueError("Invalid status object")
            severity = status.get("statusSeverity")
            description = status.get("statusSeverityDescription")
            if (type(severity) is not int or not 0 <= severity <= 20
                    or not isinstance(description, str) or not description.strip()):
                raise ValueError("Invalid severity or description")
    return data


@dataclass(frozen=True)
class UploadResult:
    key: str
    sha256: str
    created: bool


class SnapshotStore:
    def __init__(self, config, client=None, sleep=time.sleep):
        config.validate()
        self.config = config
        self.client = client if client is not None else create_client(config)
        self.sleep = sleep

    def request(self, operation):
        """Share this adapter's bounded retry policy with execution manifests."""
        return self._retry(operation)

    def read_snapshot(self, key, expected_sha256=None, expected_source_file=None):
        """Read and verify a snapshot for replay or a controlled local download."""
        if not isinstance(key, str) or not key.startswith(self.config.prefix + "/"):
            raise ValueError("Object is outside the raw snapshot prefix")
        def read():
            response = self.client.get_object(Bucket=self.config.bucket, Key=key)
            body = response["Body"]
            try:
                payload = body.read(MAX_SNAPSHOT_BYTES + 1)
            finally:
                body.close()
            metadata = response.get("Metadata", {})
            digest = hashlib.sha256(payload).hexdigest()
            if (digest != metadata.get("sha256") or len(payload) != response.get("ContentLength")
                    or (expected_sha256 is not None and digest != expected_sha256)
                    or (expected_source_file is not None and metadata.get("source-file") != expected_source_file)):
                raise IntegrityError("Downloaded snapshot bytes or lineage differ")
            validate_snapshot(payload)
            return payload, metadata
        return self.request(read)

    def _retry(self, operation):
        from botocore.exceptions import (ClientError, ConnectionClosedError,
                                         ConnectTimeoutError, EndpointConnectionError,
                                         ReadTimeoutError)
        for attempt in range(1, self.config.attempts + 1):
            try:
                return operation()
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "Unknown")
                status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
                if code in {"404", "NoSuchKey", "NotFound", "PreconditionFailed", "412"}:
                    raise
                transient = status in {409, 429, 500, 502, 503, 504} or code in {
                    "SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable",
                    "ConditionalRequestConflict"}
                if not transient or attempt == self.config.attempts:
                    raise StorageError("S3 request failed") from None
            except (ConnectionClosedError, ConnectTimeoutError,
                    EndpointConnectionError, ReadTimeoutError):
                if attempt == self.config.attempts:
                    raise StorageError("S3 retry budget exhausted") from None
            emit("snapshot_retry", attempt=attempt)
            self.sleep(min(0.25 * 2 ** (attempt - 1), 2))

    def upload_file(self, path, source_file=None):
        path = Path(path)
        if path.stat().st_size > MAX_SNAPSHOT_BYTES:
            raise ValueError("Snapshot exceeds 5 MiB")
        match = re.fullmatch(r"tube_status_(\d{8}_\d{6})\.json", path.name)
        if not match:
            raise ValueError("Snapshot filename must contain its collection timestamp")
        captured = datetime.strptime(match[1], "%Y%m%d_%H%M%S")
        return self.upload_bytes(path.read_bytes(), source_file or f"data/raw/{path.name}",
                                 captured.isoformat(), "Europe/London")

    def upload_bytes(self, payload, source_file, snapshot_time, timezone="UTC"):
        validate_snapshot(payload)
        source = PurePosixPath(source_file)
        if (not source_file.isascii() or len(source_file) > 300
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", source_file)
                or source.is_absolute() or ".." in source.parts):
            raise ValueError("Lineage must be a portable relative source path")
        captured = datetime.fromisoformat(snapshot_time)
        if timezone not in {"UTC", "Europe/London"}:
            raise ValueError("Unsupported snapshot timezone")
        digest = hashlib.sha256(payload).hexdigest()
        key = (f"{self.config.prefix}/{captured:%Y/%m/%d}/"
               f"{source.stem}-{digest}.json")
        metadata = {"sha256": digest, "source-file": source_file,
                    "snapshot-time": snapshot_time, "snapshot-timezone": timezone,
                    "schema-version": "1"}
        from botocore.exceptions import ClientError

        def verify():
            def read_and_verify():
                response = self.client.get_object(Bucket=self.config.bucket, Key=key)
                body = response["Body"]
                try:
                    actual = body.read(MAX_SNAPSHOT_BYTES + 1)
                finally:
                    body.close()
                if (hashlib.sha256(actual).hexdigest() != digest
                        or response.get("Metadata") != metadata
                        or response.get("ContentLength") != len(payload)):
                    raise IntegrityError("Stored snapshot bytes or lineage differ")
            self._retry(read_and_verify)

        # Conditional PUT avoids a check/write race and requires no ListBucket.
        created = True
        try:
            self._retry(lambda: self.client.put_object(
                Bucket=self.config.bucket, Key=key, Body=payload,
                ContentType="application/json", Metadata=metadata,
                ServerSideEncryption="AES256", IfNoneMatch="*",
                ChecksumSHA256=base64.b64encode(bytes.fromhex(digest)).decode("ascii")))
        except ClientError as error:
            if error.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
                raise StorageError("S3 conditional write failed") from None
            created = False  # Another writer, or an ambiguous retried success.
        verify()
        emit("snapshot_uploaded" if created else "snapshot_duplicate", key=key, sha256=digest)
        return UploadResult(key, digest, created)


def archive_snapshot_if_enabled(path):
    """Best-effort mirror: cloud failure must never break the local pipeline.

    The durable local raw file remains available for an explicit replay.
    """
    if os.getenv("S3_ENABLED", "false").lower() != "true":
        return None
    try:
        return SnapshotStore(StorageConfig.from_env()).upload_file(path)
    except Exception as error:
        emit("snapshot_archive_failed", error_type=type(error).__name__,
             replay_required=True)
        return None
