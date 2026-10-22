"""S3 conditional-write leases for one logical Scheduler run.

No extra database is required. A completed run is replayed without fetching TfL
again. Leases recover invocations killed by the 120-second Lambda timeout.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json

from botocore.exceptions import ClientError
from src.storage.s3_storage import StorageError

LEASE_SECONDS = 150
CONTROL_PREFIX = "control/tfl/tube/runs"


class ExecutionInProgress(StorageError):
    pass


@dataclass(frozen=True)
class Lease:
    key: str
    owner: str
    etag: str
    record: dict


def conditional_conflict(error):
    return isinstance(error, ClientError) and error.response["Error"]["Code"] in {"412", "PreconditionFailed"}


class ExecutionRegistry:
    def __init__(self, store, now=None):
        self.store = store
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _read(self, key):
        def read():
            response = self.store.client.get_object(Bucket=self.store.config.bucket, Key=key)
            body = response["Body"]
            try:
                raw = body.read(16385)
            finally:
                body.close()
            if len(raw) > 16384:
                raise StorageError("Execution manifest exceeds limit")
            record = json.loads(raw)
            if record.get("version") != 1 or record.get("state") not in {"PROCESSING", "FAILED", "COMPLETE"}:
                raise StorageError("Invalid execution manifest")
            return record, response["ETag"]
        return self.store.request(read)

    def _put(self, key, record, **condition):
        return self.store.request(lambda: self.store.client.put_object(
            Bucket=self.store.config.bucket, Key=key,
            Body=json.dumps(record, sort_keys=True, separators=(",", ":")).encode(),
            ContentType="application/json", ServerSideEncryption="AES256", **condition))

    def claim(self, identity, scheduled, owner):
        run_id = hashlib.sha256(identity.encode()).hexdigest()
        key = f"{CONTROL_PREFIX}/{scheduled:%Y/%m/%d}/{run_id}.json"
        now = self.now()
        record = {"version": 1, "state": "PROCESSING", "owner": owner,
                  "run_id": run_id, "scheduled_time": scheduled.isoformat(),
                  "lease_expires": (now + timedelta(seconds=LEASE_SECONDS)).isoformat()}
        try:
            response = self._put(key, record, IfNoneMatch="*")
            return Lease(key, owner, response["ETag"], record), None
        except ClientError as error:
            if not conditional_conflict(error):
                raise StorageError("Execution claim failed") from None
        previous, etag = self._read(key)
        if previous.get("run_id") != run_id:
            raise StorageError("Execution identity mismatch")
        if previous["state"] == "COMPLETE":
            return None, previous["result"]
        if previous["state"] == "PROCESSING":
            # Recover an ambiguous successful write from this same invocation.
            if previous["owner"] == owner:
                return Lease(key, owner, etag, previous), None
            if datetime.fromisoformat(previous["lease_expires"]) > now:
                raise ExecutionInProgress("Another invocation owns this execution")
        try:
            response = self._put(key, record, IfMatch=etag)
        except ClientError as error:
            if conditional_conflict(error):
                raise ExecutionInProgress("Execution lease changed concurrently") from None
            raise StorageError("Execution recovery failed") from None
        return Lease(key, owner, response["ETag"], record), None

    def finish(self, lease, result=None, error_type=None):
        record = {**lease.record, "state": "FAILED" if error_type else "COMPLETE",
                  "finished_at": self.now().isoformat()}
        if error_type:
            record["error_type"] = error_type
        else:
            record["result"] = result
        try:
            self._put(lease.key, record, IfMatch=lease.etag)
        except ClientError as error:
            if not conditional_conflict(error):
                raise StorageError("Execution completion failed") from None
            # An acknowledged write may have been followed by a lost response.
            current, _ = self._read(lease.key)
            if current.get("owner") != lease.owner or current != record:
                raise StorageError("Execution lease was lost") from None
