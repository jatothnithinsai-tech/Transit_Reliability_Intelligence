# S3 snapshots and the existing local analytics pipeline

The Lambda archives raw TfL observations only. PostgreSQL, historical loading and Power BI stay local. There is no inbound database exposure, cloud PostgreSQL deployment, background S3-to-database synchronizer or Power BI gateway in this extension.

After an approved cloud deployment and authenticated profile setup, use the verified downloader with storage explicitly enabled in the invoking process. This example changes only that terminal's environment; it does not change the local scheduler's `.env`:

```powershell
$env:S3_ENABLED='true'
$env:S3_MODE='aws'
$env:S3_ALLOW_AWS='true'
$env:S3_BUCKET='YOUR_APPROVED_BUCKET'
$env:AWS_REGION='eu-west-2'
.\.venv\Scripts\python.exe scripts/download_cloud_snapshot.py --key 'raw/tfl/tube/YYYY/MM/DD/OBJECT.json' --sha256 'EXPECTED_DIGEST'
```

Use the real key/digest from the completed execution manifest, not the placeholders. This command performs GetObject, checks the content hash, JSON and metadata, and writes to ignored `data/cloud_inbox/`. A sidecar preserves S3 key, collection timestamp, timezone, source path and checksum. File names include object identity and digest so equal payloads at different collection times retain separate lineage. Existing different local files are never overwritten. The command does not write `data/raw/`, replace the processed CSV, run the ETL, connect to PostgreSQL or refresh Power BI. If interrupted during local file creation, inspect the incomplete file before retrying; the downloader deliberately refuses to overwrite differing bytes.

AWS CLI `s3 sync` can alternatively land a prefix into an isolated ignored inbox, but it does not perform this application's SHA-256/lineage validation. Do not sync directly over `data/raw/` and do not use a delete option. Never sync `.env` or a whole project directory to the bucket.

For a controlled local import, preserve these mappings:

| Cloud field | Existing local contract |
|---|---|
| Raw JSON bytes | Keep byte-for-byte; do not edit nested TfL statuses |
| UTC capture timestamp in metadata | Convert to Europe/London before forming legacy `tube_status_YYYYMMDD_HHMMSS.json` |
| Scheduled time | Audit context only; it is not the local snapshot_time |
| Full cloud source key/execution ID/checksum | Retain the inbox sidecar; local history source_file must point to the retained compatible raw file |
| Line/status fields | Same transformer/quality rules and four-column database uniqueness key |

The current transformer intentionally selects the latest compatible local raw filename and overwrites its one processed CSV. An arbitrary older downloaded cloud file will not be imported merely by placing it in the inbox. A backfill must select that specific source and use isolated CSV staging through the existing transformer, validator and loader while excluding overlapping local runs. The prior local verification demonstrated this controlled method for a retained historical snapshot. An automated multi-file cloud backfill utility is **not implemented** and is not claimed as tested.

When preparing a legacy compatible raw file, check for a filename collision first. Refuse to overwrite a different existing file, including around daylight-saving changes. The legacy format has second precision and London DST ambiguity; the cloud timestamp retains UTC microseconds. Do not silently round several cloud observations into different claims about the same legacy observation. Preserve the original cloud file/sidecar and resolve any collision before loading.

Run the existing quality validation and transactional loader against the specifically prepared staging CSV; replaying an already loaded identity should insert zero rows. Then use the read-only lineage audit and SQL views to verify counts and source-file existence before refreshing Power BI Desktop. Daily disruption and sampled percentages retain their current definitions; cloud ingestion does not turn sampled percentages into actual uptime. Reset the terminal's S3 flags to false before returning to ordinary local operation.
