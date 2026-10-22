# Architecture and operations

The implemented system is local: TfL REST API → historical JSON → processed CSV → PostgreSQL → SQL views → Power BI import. Its operating cost for AWS is £0 because no AWS services are deployed. The optional S3 adapter is a separate archival concern and cannot determine local ETL success.

| Component | Responsibility and failure boundary |
|---|---|
| `src/ingestion/save_raw_status.py` | GET with connect/read timeouts, three retries for transient failures, Retry-After support; atomic UTF-8 JSON write using flush, fsync and replacement |
| `src/transformation/transform_tube_status.py` | Select latest filename timestamp, flatten every service status, retain collection timestamp and original relative path; atomically replace current processed CSV |
| `src/quality/validate_tube_status.py` | Reject absent columns, required nulls, invalid integer severity, duplicate status identity and invalid timestamps |
| `src/loading/load_tube_status.py` | Verify original raw source, upsert reference lines, insert history with conflict protection, repair differing lineage; one transaction per CSV with rollback and close on failure |
| `src/pipeline/run_pipeline.py` | Sequential subprocess stages using the active interpreter, fixed project working directory, 180-second stage timeout, fail-fast behavior and execution audit |
| PostgreSQL | Dedicated session advisory lock; monitoring states RUNNING/SUCCESS/FAILED and stale-run health view |
| Power BI | Existing PBIP/PBIR/TMDL import model; SQL data updates become visible after Desktop refresh |
| `src/storage/s3_storage.py` | Optional immutable conditional PUT, SHA-256 and full readback, structured JSON events, bounded retry, explicit replay |

Raw snapshots are the durable recovery boundary. The processed CSV is an overwriteable staging artifact. PostgreSQL history is retained across runs. A failed database transaction can be retried using the same processed source; the uniqueness index prevents duplicate status identities. The standard controller fetches a new snapshot on its next run, so operators must explicitly replay a previously failed load if complete history is required.

The scheduler was inspected on 21 October 2026: task `TfL Transit Reliability Pipeline`, hourly repetition, project virtual environment, correct root working directory, ready state, and last task result 0. `StartWhenAvailable` is enabled. The task uses IgnoreNew behavior and the controller independently obtains a PostgreSQL session advisory lock. The task's 72-hour limit is broad; controller subprocess timeouts provide the practical stage limit. We did not modify the task.

Exit codes: 0 success; 1 failed stage/monitoring; 2 overlap prevented. Database connection failure stops the monitored controller before ingestion. A failed stage prevents later stages; successful lock acquisition is paired with release even when initialization or auditing fails. Database audit failures propagate. Monitoring records only exception class names, while local logs provide diagnostic traces. HTTP errors in ingestion are sanitized so a TfL key in a request URL cannot appear in the emitted traceback.

Operational review can use:

```sql
SELECT * FROM monitoring.v_pipeline_run_health ORDER BY started_at DESC LIMIT 20;
SELECT * FROM analytics.vw_operational_kpi_summary;
```

Stale runs can remain after a process is killed before final audit update. Session termination releases the advisory lock, but does not retrospectively repair the RUNNING record. Do not change run status until confirming the process ended. There is no paging service or automated local log rotation. Logs and original data remain ignored rather than being deleted by cleanup jobs.

The local timestamp convention is the filename's Europe/London wall time. PostgreSQL currently uses `Europe/London`; new installations must use the same convention. Daylight-saving autumn ambiguity and second-resolution filename collisions remain limitations of the original local format. Lambda uses explicit UTC event timestamps. Transformation captures only the first validity period for each status and stores service observations rather than uniquely identified incidents.

The slicer dimension filters line reliability and major-disruption aggregates. Daily and severity views are global aggregates without a line key, so their visuals are deliberately isolated from line selection. Global cards also retain the global sample scope. This avoids presenting preaggregated global data as if it were selected-line data.

Future cloud architecture is described separately in [the deployment plan](aws_deployment_plan.md). It supplies an S3 raw landing zone, not cloud PostgreSQL, historical import automation, or a Power BI refresh gateway.
