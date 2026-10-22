# Completion report — 21 October 2026

The local engineering pipeline and optional AWS-compatible archival are implemented and verified. **AWS deployment status: NOT DEPLOYED.** No AWS account login, real AWS credentials, paid resources, Git commit or GitHub push was used. Budget remains £0 for AWS services.

Completed:

- Preserved the existing ETL controller, scheduler, PostgreSQL history, SQL view definitions and Power BI report/model source. All 72 fingerprinted pre-existing protected files remained byte-for-byte unchanged.
- Added a Boto3 snapshot adapter, disabled by default, with traceable content-hash keys, portable lineage metadata, JSON validation, conditional writes, SHA-256 verification, full readback, structured events, bounded retries and explicit replay.
- Kept local ETL independent of cloud availability. The adapter uses dummy credentials in loopback-only local mode. Real AWS mode requires two explicit enablement settings and was never used.
- Added a Lambda entry point and real ZIP build process, plus Terraform S3, Lambda, EventBridge, CloudWatch, IAM, optional Secrets Manager, failure queues and alert topic. Scheduling and deployment authorization default to false.
- Replaced the empty README with setup, architecture, KPI interpretation, testing and portfolio navigation. Added all eight requested engineering guides, AWS Educate guidance and this report.
- Added the missing PostgreSQL Python dependency, development dependencies, a secret-safe environment template, publication exclusions, a schema-only PostgreSQL reference and reproducible audit/check scripts.
- Fixed a confirmed disclosure risk: production ingestion tracebacks now sanitize Requests errors that could otherwise contain the TfL app key in a URL.
- Recovered one confirmed historical-loading gap: the retained 15 October 22:06:05 snapshot contributed 12 history records through isolated staging. The latest processed CSV and existing rows were preserved.

Actual results:

| Verification | Final result |
|---|---|
| Original suite | 43 passed before changes |
| Final automated suite | **66 passed, 0 failed, 0 errors, 0 skipped**; external sockets blocked |
| Local S3-compatible tests | 19 passed using Moto, including Lambda-to-S3 round trip and duplicate event replay |
| Full live local pipeline | Passed: 11 fetched line objects, 11 validated records, 11 database inserts, successful monitoring and lock release |
| Duplicate replay in PostgreSQL | 0 new history rows; 0 lineage changes |
| Raw/history/analytics audit | All 29 retained raw files reconcile to 324 history records and 319 line observations across 29 collection times and 11 lines |
| KPI totals | 236 Good Service + 83 disrupted; 73.98% / 26.02%, sampled observations |
| Power BI definition checks | PBIR schemas/bindings/interactions passed; 12 tables and 17 measures parsed |
| Power BI live DAX | Passed against an open import model: global, per-line, daily and distribution queries; global metrics invariant under line context |
| Terraform | 1.13.5; signed AWS provider 6.69.1; backend-free init, formatting and schema validation passed |
| Lambda package | Built locally; isolated ZIP imports passed; actual AWS runtime not executed |
| Dependencies | `pip check` passed |
| Security review | No detected secret/sensitive-file findings or candidates over 10 MiB; sensitive-path ignore probes passed |

The first live pipeline attempt was blocked by sandbox networking. It correctly recorded FAILED and released its lock. The rerun with permitted TfL access passed. That failed audit row is retained rather than hidden. Local Windows authentication similarly required running the read-only DAX validation outside the sandbox; the resulting queries passed.

Created files, grouped for review:

| Area | Files |
|---|---|
| Storage and cloud source | `src/storage/__init__.py`, `src/storage/s3_storage.py`, `src/cloud/__init__.py`, `src/cloud/lambda_handler.py` |
| Tests/dependencies | `tests/test_storage.py`, `tests/test_cloud.py`, `requirements-dev.txt`, `requirements-lambda.txt` |
| Infrastructure | `infra/aws/versions.tf`, `variables.tf`, `storage.tf`, `main.tf`, `monitoring.tf`, `outputs.tf`, `terraform.tfvars.example`, `.terraform.lock.hcl` |
| Utilities | `scripts/build_lambda.py`, `bootstrap_terraform.ps1`, `replay_snapshot.py`, `audit_project.py`, `security_review.py`, `run_checks.py` |
| Schema reference | `sql/00_schema_reference.sql` (exported from existing PostgreSQL, without rows, owners or grants) |
| Documentation | `docs/architecture.md`, `data_dictionary.md`, `kpi_definitions.md`, `testing.md`, `aws_deployment_plan.md`, `interview_walkthrough.md`, `aws_educate_guide.md`, `completion_report.md` |
| Evidence | JSON files under `docs/validation/`; built Lambda ZIP and file backups remain ignored locally |

Modified existing files: `README.md`, `.gitignore`, `.env.example`, `requirements.txt`, `src/ingestion/save_raw_status.py`. Existing generated Power BI validation JSON files were refreshed with actual results. Original SQL analytics, report definitions and semantic model definitions were not edited. The original requirements file was UTF-16 and was normalized to UTF-8 when adding the missing dependency. Local file backups are under ignored `backups/completion_20261021/`; earlier Power BI backups remain intact.

Limitations and user actions:

- **Refresh Power BI Desktop to show the latest database observations.** The queried open model still showed 23 collection times and a latest imported observation of 13:34 model time. Its calculations passed, but this session did not refresh or save the dashboard. No PBIX or screenshots existed inside the workspace; external PBIX files were untouched.
- Moto does not validate real AWS authorization, Linux runtime behavior, service quotas or deployed alarms. Terraform plan/apply and cloud deployment were deliberately not run. The SNS topic has no configured subscriber in the future design.
- Sampled percentages do not represent actual uptime. The original local filename timestamps retain second-resolution/DST ambiguity, and the transformer uses only the first validity period. Power BI refresh, upload replay and recovery of a future failed load require explicit action; there is no persistent replay queue.
- A clean environment installation and schema restoration into another database were not performed. The existing environment passed dependency consistency checks. The Power BI preservation validator depends on workstation-local ignored backup/cache files.
- AWS Educate exercises require the user to register and complete whichever free labs are available; no lab completion is claimed. No AWS action is necessary to use or demonstrate this project locally.

GitHub publication is prepared, but the repository currently has no commits and all publishable source is untracked. Review `git status` and `scripts/security_review.py` results, stage reviewed source/docs, inspect the staged diff, choose a license if appropriate, and approve publication separately. Do not force-add ignored `.env`, datasets, logs, caches, backups, PBIX files, deployment ZIPs or Terraform state. A final staged-content review is still required before the first commit/push; no approval to publish has been inferred.
