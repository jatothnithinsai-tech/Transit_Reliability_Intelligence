# Cloud ingestion operations and troubleshooting

These procedures describe the future approved environment. **Nothing is deployed now.** Keep the existing local scheduler and PostgreSQL pipeline as they are.

Successful events: `ingestion_success`, `snapshot_uploaded`, and the embedded `SnapshotsUploaded` metric. Expected duplicate events: `ingestion_duplicate`. Storage retries emit `snapshot_retry`. Failed executions emit sanitized `ingestion_failed`; inability to update an execution marker emits `execution_state_update_failed`. Exceptions record type, not request URLs or credentials. Source keys identify snapshots; collection and scheduled timestamps are distinct.

Execution states are PROCESSING, COMPLETE and FAILED under `control/tfl/tube/runs/`. A completed run returns its saved result after verifying its raw object. A concurrent active lease causes a retriable handler failure; a failed or expired lease can be reclaimed conditionally. A lease lasts 150 seconds; Lambda timeout is 120 seconds. Control retention is seven days. Do not delete or manually edit manifests to force re-execution; investigate the object and logs before any approved repair.

Scheduler delivery retries and Lambda asynchronous execution retries cover different boundaries. Scheduler attempts delivery at most three times total within one hour and sends exhausted delivery failures to the delivery DLQ. Lambda independently retries execution twice within one hour and sends exhausted executions to the invocation DLQ. Retries do not imply exactly-once raw object creation. A timeout between upload and manifest completion can leave an orphan observation. No automatic destructive cleanup or DLQ redrive job is installed.

| Symptom | Check and interpretation |
|---|---|
| No invocations | Schedule state, group/name, execution-role trust/account/group ARN and InvokeFunction scope; confirm the approved schedule was enabled |
| Invocations but no successful snapshot metric | Lambda Errors/Duration/Throttles, sanitized logs, both DLQs, TfL response validation and S3 prefix permissions |
| AccessDenied | Correct bucket, role and raw/control prefix; optional secret read grant; no ListBucket permission is expected |
| Timeout or HTTP 429/5xx | Configured bounded retries; upstream availability; Lambda duration and timeout; preserve original raw evidence |
| Duplicate or ExecutionInProgress | Compare scheduled time and logical identity; inspect lease expiry and owner; distinguish attempted execution ID from logical run identity |
| Integrity failure | Compare SHA-256, length and source metadata; do not overwrite an existing local file or silently bless changed bytes |
| Alarm but no notification | SNS topic has no subscriber by default; subscription and confirmation have not been configured |
| Metrics absent | Inspect raw EMF JSON in the log group; Namespace TransitReliability, metric SnapshotsUploaded and PipelineName must match the alarm |

After a future deployment, read-only examples (replace resource names/profile as appropriate):

```powershell
aws scheduler get-schedule --group-name transit-reliability --name transit-reliability-hourly --region eu-west-2
aws lambda get-function-configuration --function-name transit-reliability-ingestion --region eu-west-2
aws logs tail /aws/lambda/transit-reliability-ingestion --since 1h --region eu-west-2
aws cloudwatch describe-alarms --alarm-name-prefix transit-reliability --region eu-west-2
```

Avoid printing or sharing secret values or full failure payloads. The standard runtime metrics provide requests, failures, duration and throttles. The single custom upload metric measures actual completed capture events, unlike an invocation counter. Logs retain 14 days; both queues retain seven days. Current raw objects retain 90 days. Lifecycle expiration is eventual and versioning/noncurrent retention can extend storage beyond the current object's expiration.

Cost monitoring is not a hard spending cap. A future deployment should have a separately approved billing alert and a confirmed notification destination. Neither is created without that approval. Check actual daily usage and stop scheduling before investigating unexpected growth. Disabled scheduling stops new scheduled work but does not remove alarm, stored-data, secret or retained-version charges.

Local/offline checks:

```powershell
.\.venv\Scripts\python.exe scripts/run_checks.py
.\.venv\Scripts\python.exe scripts/build_lambda.py --installed
.\.tools\terraform-1.13.5\terraform.exe -chdir=infra/aws fmt -check -recursive
.\.tools\terraform-1.13.5\terraform.exe -chdir=infra/aws validate
.\.tools\terraform-1.13.5\terraform.exe -chdir=infra/aws test
.\.venv\Scripts\python.exe scripts/estimate_aws_costs.py
```

The last command uses cached public price lists and makes no network requests. `--refresh` fetches unsigned price-list JSON from AWS's public website, without credentials or provisioning. Tests use Moto/intercepted HTTP and block external socket connections. Terraform tests use mocked providers and plan-only runs. Test-runner logging is isolated so simulated failures do not pollute the operational pipeline log.
