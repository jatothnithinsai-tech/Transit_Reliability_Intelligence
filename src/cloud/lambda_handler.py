"""EventBridge -> TfL -> S3. Does not attempt to connect to a local database."""
import json
import logging
import os
import hashlib
import re
import uuid
from datetime import datetime, timezone

from src.ingestion.tfl_client import fetch_tube_status
from src.storage.s3_storage import SnapshotStore, StorageConfig, emit, validate_snapshot
from src.cloud.execution_registry import ExecutionRegistry


def fetch_snapshot(api_key=None):
    data = fetch_tube_status(api_key, timeout=(3, 10), cloud=True)
    validate_snapshot(encode_snapshot(data))
    return data


def encode_snapshot(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def parse_event(event):
    """Accept Scheduler context input and preserve the previous rule payload."""
    if not isinstance(event, dict):
        raise ValueError("Expected a scheduled event object")
    if "scheduled_time" in event:
        stamp, execution_id = event["scheduled_time"], event.get("execution_id")
        schedule = event.get("schedule_arn", "")
        if not isinstance(schedule, str) or not re.fullmatch(
                r"arn:aws:scheduler:[a-z0-9-]+:[0-9]{12}:schedule/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", schedule):
            raise ValueError("Invalid Scheduler ARN")
        expected = os.getenv("EXPECTED_SCHEDULE_ARN")
        if expected and schedule != expected:
            raise ValueError("Unexpected schedule")
        logical_source = schedule
    else:
        stamp, execution_id = event.get("time"), event.get("id")
        logical_source = "legacy-eventbridge:" + str(execution_id)
    if not isinstance(execution_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", execution_id):
        raise ValueError("Invalid execution ID")
    if not isinstance(stamp, str):
        raise ValueError("Missing scheduled timestamp")
    scheduled = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if scheduled.tzinfo is None:
        raise ValueError("Scheduled timestamp requires a timezone")
    scheduled = scheduled.astimezone(timezone.utc)
    return scheduled, execution_id, logical_source + "|" + scheduled.isoformat()


def success_metric():
    # EMF publishes one low-cardinality custom metric via logs, not an API call.
    print(json.dumps({"_aws": {"Timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        "CloudWatchMetrics": [{"Namespace": "TransitReliability", "Dimensions": [["PipelineName"]],
        "Metrics": [{"Name": "SnapshotsUploaded", "Unit": "Count"}]}]},
        "PipelineName": os.getenv("PIPELINE_NAME", "transit-reliability-ingestion"),
        "SnapshotsUploaded": 1}), flush=True)


def read_api_key(secret_arn):
    import boto3
    # Terraform grants access only to the separately populated secret ARN.
    value = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    key = json.loads(value["SecretString"])["TFL_API_KEY"]
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Secret requires a non-empty TFL_API_KEY")
    return key


def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    config = StorageConfig.from_env()
    # Validate before fetching TfL or resolving a secret: disabled means no I/O.
    config.validate()
    lease = None
    registry = None
    try:
        scheduled, event_id, identity = parse_event(event)
        store = SnapshotStore(config)
        registry = ExecutionRegistry(store)
        owner = getattr(context, "aws_request_id", None) or str(uuid.uuid4())
        lease, previous = registry.claim(identity, scheduled, owner)
        if previous is not None:
            store.read_snapshot(previous["key"], previous["sha256"], previous["source_file"])
            emit("ingestion_duplicate", execution_id=event_id)
            return {**previous, "created": False}
        api_key = read_api_key(os.environ["TFL_SECRET_ARN"]) if os.getenv("TFL_SECRET_ARN") else None
        data = fetch_snapshot(api_key)
        captured = datetime.now(timezone.utc)
        logical_run_id = hashlib.sha256(identity.encode()).hexdigest()
        source = f"lambda/tube_status_{captured:%Y%m%d_%H%M%S_%f}_{logical_run_id[:16]}_{event_id}.json"
        payload = encode_snapshot(data)
        # Storage validates again, including when fetch_snapshot is substituted.
        result = store.upload_bytes(payload, source, captured.isoformat())
        response = {"key": result.key, "sha256": result.sha256, "created": result.created,
                    "snapshot_time": captured.isoformat(), "scheduled_time": scheduled.isoformat(),
                    "source_file": source, "execution_id": event_id,
                    "logical_run_id": logical_run_id, "schedule_arn": event.get("schedule_arn")}
        registry.finish(lease, response)
        success_metric()
        emit("ingestion_success", execution_id=event_id, created=result.created, key=result.key)
        return response
    except Exception as error:
        if lease is not None and registry is not None:
            try:
                registry.finish(lease, error_type=type(error).__name__)
            except Exception as state_error:
                emit("execution_state_update_failed", error_type=type(state_error).__name__)
        # Never forward requests exceptions: their URLs may contain app_key.
        emit("ingestion_failed", error_type=type(error).__name__)
        raise RuntimeError("TfL cloud ingestion failed; inspect sanitized logs") from None
