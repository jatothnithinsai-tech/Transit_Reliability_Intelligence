# Data dictionary

| Dataset | Grain / key | Important fields |
|---|---|---|
| `data/raw/tube_status_YYYYMMDD_HHMMSS.json` | One API response per collection | TfL line objects with nested statuses; timestamp comes from filename, not TfL event start |
| `data/processed/tube_status_clean.csv` | One flattened status; latest snapshot only | 13 columns including snapshot, line, severity, reason, validity and source_file |
| `staging.tube_lines` | `line_id` primary key | `line_name`, `created_at`, `updated_at`; 11 observed Tube lines |
| `staging.tube_status_history` | `status_id` bigint identity; unique index on snapshot_time, line_id, status_severity, status_description | Historical statuses, validity, lineage and loading timestamp |
| `monitoring.pipeline_runs` | `run_id` UUID | started_at, finished_at, status, failed_step, error_message |
| `monitoring.v_pipeline_run_health` | One monitored run | Duration and HEALTHY/FAILED/IN_PROGRESS/STALE; stale RUNNING threshold 15 minutes |

| History field | Meaning |
|---|---|
| `snapshot_time` | timestamptz collection time; local filename parsed using database London timezone |
| `line_id` | TfL identifier; foreign key to tube_lines |
| `status_severity` | Integer category code 0–20; 10 denotes Good Service; not a linear severity score |
| `status_description` | TfL category label; multiple categories may coexist for one line/time |
| `reason` | Optional text explaining the status |
| `disruption_from`, `disruption_to` | Optional validity endpoints from the first reported validity period |
| `is_now` | Optional validity flag; empty stays SQL NULL |
| `source_file` | Portable path such as `data/raw/tube_status_20261021_143936.json`; original file must exist at load time |
| `loaded_at` | Database ingestion time, distinct from collection and disruption times |

The transformer also retains mode, disruption category and disruption description in CSV; the current loader does not persist these extra three fields. It maps CSV `from_date`/`to_date` to database `disruption_from`/`disruption_to`. Raw JSON remains the complete source of truth. Status identity intentionally omits reason/validity: a duplicate equal identity is ignored on replay, even if descriptive fields differ. Reason changes within the same collection identity are not versioned.

| Analytics view | Grain and interpretation |
|---|---|
| `vw_line_snapshot_status` | One line and collection time; status_records, was_disrupted, was_good_service |
| `vw_line_reliability` | One line; observed counts and 0–100 percentages |
| `vw_daily_disruption_trends` | One London local date; collection times, line observations and disruption percentage |
| `vw_disruption_severity` | One severity code/description; raw record counts and record shares |
| `vw_major_disruptions_by_line` | One line; distinct line/time major-category union and overlapping category counts |
| `vw_operational_kpi_summary` | One global summary row; monitored lines, collection times, observation counts, percentages and range |

S3 keys have the form `raw/tfl/tube/YYYY/MM/DD/<source-stem>-<full-sha256>.json`. The full hash refers to exact UTF-8 source bytes. Metadata includes sha256, source-file, snapshot-time, snapshot-timezone and schema-version. Metadata paths contain no absolute workstation directory or credentials. New data and a new source stem produce a new key; replay of the same bytes and lineage returns a verified duplicate.

See [KPI definitions](kpi_definitions.md) for the distinction between status records, line observations, collection times, incidents and uptime.
