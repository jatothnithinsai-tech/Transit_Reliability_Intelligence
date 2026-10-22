# AWS integration completion — 22 October 2026

**Status: IMPLEMENTED AND TESTED LOCALLY; NOT DEPLOYED.** No AWS service resource was created, modified or deleted. No account login, credential disclosure, Git staging, commit or push was performed. Public AWS London price-list files were retrieved unsigned to verify the cost calculation.

| Check | Actual result |
|---|---|
| Python automated suite | **96 passed, 0 failed, 0 errors, 0 skipped**; external connections blocked |
| Existing local regression coverage | Preserved and passing, including ETL/DB/monitoring, local S3 adapter and Git safety |
| New cloud coverage | Shared HTTP extraction, real intercepted 503 retry, exhausted retries, timeout settings/propagation, capped Retry-After, invalid responses, Scheduler input, source/timestamp lineage, changed-attempt duplicate handling, failed/expired leases, upload failures, secret isolation, integrity and local download safety |
| Terraform formatting/schema validation | Passed; Terraform 1.13.5 and locked AWS provider 6.69.1; 0 errors/warnings |
| Terraform mock-plan tests | **3 passed, 0 failed, 0 skipped**; architecture/security, approval guard and optional secret |
| Resource proposal | Mocked default plan contains exactly **23 create actions**; no real account-backed plan |
| Lambda package | Real ZIP built; isolated Python imports passed; source hashes match; no `.env`, private keys, native Windows extensions, PostgreSQL code or Power BI artifacts |
| Dependency consistency | `pip check` passed; runtime and all transitive Lambda dependencies locked |
| Existing data/report preservation | **88 pre-existing protected files unchanged**; SQL views and report/model source definitions retained |
| Current read-only database audit | Passed; all 44 retained snapshots reconcile to 496 status records and 484 line observations across 11 lines |
| Git safety | No staged files or detected secret candidates; ignored cloud inbox and real index inspection included |
| AWS environment | Python 3.13.7/Boto3 available; AWS CLI unavailable; no credentials, profiles or configured default region |
| Real AWS identity/eligibility/plan/runtime | **NOT VERIFIED / NOT DONE**: credentials unavailable; deployment approval withheld |

The current local scheduler continued collecting observations during this work. No local ETL rerun, historical reload or dashboard rebuild was required for this cloud-preparation task. The read-only database audit reconciled all current loaded sources. The earlier Power BI import remains separate from live PostgreSQL and still needs the user's intended Desktop refresh to show newer observations; the cloud extension does not provide a refresh gateway.

Implemented AWS components:

- True EventBridge Scheduler hourly execution with UTC context input, dedicated group/role, disabled initial state and bounded delivery retries.
- Lambda using the shared TfL client, input/JSON validation, captured-versus-scheduled timestamps, collision-resistant keys, sanitized failures and one embedded success metric.
- Private encrypted versioned S3 with two scoped prefixes, conditional execution leases, replay verification and lifecycle controls.
- Least-privilege Lambda/Scheduler roles, fourteen-day logs, four alarms, two encrypted failure queues and one alert topic.
- Optional Secrets Manager reference, disabled by default; no secret value in Terraform or the package.
- Verified downloader into an ignored local inbox; documentation for controlled integration with the unchanged PostgreSQL/Power BI workflow.

Completed execution manifests deduplicate retries even when Scheduler assigns a new attempt ID. Concurrency and crash recovery are bounded by leases and runtime limits. This is not an exactly-once transaction: a crash between raw upload and manifest completion may leave an orphan raw observation. The seven-day manifest retention defines the replay window. Automatic multi-file S3-to-PostgreSQL backfill is not implemented or claimed.

Files created:

| Area | Files |
|---|---|
| Shared ingestion and run control | `src/ingestion/tfl_client.py`, `src/cloud/execution_registry.py` |
| Utilities | `scripts/download_cloud_snapshot.py`, `scripts/estimate_aws_costs.py` |
| Tests | `tests/test_aws_ingestion.py`, `tests/test_cloud_download.py`, `infra/aws/tests/offline.tftest.hcl` |
| Infrastructure | `infra/aws/scheduler.tf` |
| Guides | `docs/aws_architecture.md`, `aws_environment.md`, `aws_operations.md`, `aws_local_integration.md`, `aws_costs.md`, `aws_readiness.md` |
| Evidence | `docs/validation/aws_environment.json`, `aws_cost_estimate.json`, `terraform_offline_tests.json`, `proposed_resources.json`, `lambda_package.json`, `aws_preservation.json`; ignored ZIP/build manifest and public-price cache |

Files modified: cloud handler, local ingestion wrapper, S3 adapter, package builder, test runner, security scanner, runtime/development requirement locks, `.env.example`, `.gitignore`, the relevant Terraform files/examples, `tests/test_cloud.py`, `tests/test_security_review.py`, README, testing guide and the existing AWS deployment guide. The wrapper's HTTP behavior remains compatible; the shared client prevents a second independent HTTP implementation. Operational ETL logging is isolated from simulated test failures. Existing configuration/source backups are retained under ignored `backups/aws_integration_20261021/`.

The proposal is **23 Terraform-managed objects in eu-west-2**: one S3 bucket and six bucket configurations, one Lambda and one async-invoke configuration, one Scheduler group and one schedule, two IAM roles and two inline policies, one log group, four alarms, two SQS queues, and one SNS topic. One optional secret would make 24; no subscriber or billing alert is included. Exact addresses/actions: [resource proposal](validation/proposed_resources.json). Names and future deployment/rollback prerequisites: [deployment plan](aws_deployment_plan.md).

Expected cost: the current London regional calculation is approximately **US$0.72/month before exclusions**; propose **US$1–$3/month** as planning allowance for 720 hourly runs, 128 MB/2-second average duration, 20 KiB snapshots, 90-day raw retention, fourteen-day logs, four alarms and one custom metric. No Free Tier or credits are deducted. Optional Secrets Manager adds roughly $0.40/month plus reads. Taxes, currency conversion, retries, extra downloads and growth are excluded; no hard cap is claimed. See [verified regional rates and assumptions](aws_costs.md).

Ready for review and a future account-backed plan: application source, pinned deployment artifact, Terraform/security configuration and operating procedures. Not deployed or proven operational: actual Lambda/Linux runtime, AWS IAM enforcement, Scheduler delivery, CloudWatch publication/notifications, account quotas, billing eligibility and real AWS integration. Account identity and a real plan cannot run because no credentials/profile are configured. No AWS credentials are requested in chat.

**Single next action:** approve the proposed eu-west-2 resource list and US$1–$3/month allowance, and identify the authenticated AWS profile/target account to use. Keep deployment_authorized=false and schedule_enabled=false until approval. That approval permits the next identity/quota checks and reviewed real plan; this report does not claim a deployment has happened.
