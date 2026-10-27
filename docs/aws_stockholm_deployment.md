# Live AWS ingestion in Stockholm

On 26 October 2026, the existing ingestion infrastructure was deployed in
`eu-north-1` using Terraform 1.13.5, AWS provider 6.69.1 and Python 3.13.15.
London CloudShell creation was blocked by an organization service control policy.
Stockholm deployment succeeded without changing that policy.

## What is running

EventBridge Scheduler invokes `transit-reliability-ingestion` hourly. Lambda
fetches the TfL Tube status API and writes immutable JSON snapshots to a private,
encrypted, versioned S3 bucket. Execution manifests support idempotent retries.
Two failure queues, four CloudWatch alarms, an SNS topic and retained logs are
provisioned. The initial apply created 23 Terraform resources. A reviewed second
apply updated only the schedule state and freshness-alarm action setting.

This deployment archives raw data. It does not load PostgreSQL, run the full local
ETL or refresh Power BI. Existing local analytics and dashboard remain separate.
SNS has no confirmed notification subscriber yet, so alarms do not notify a
person. Automatic Scheduler delivery was verified using a temporary one-minute interval;
the original enabled hourly schedule was restored afterward. This verifies actual
Scheduler-to-Lambda execution rather than only manual invocation.

## Verified results

- Terraform formatting and validation passed; all three mocked tests passed.
- Initial account-backed plan: 23 additions, no changes or deletions.
- Live Lambda invocation returned HTTP 200 with no function error.
- Snapshot contained 11 Tube lines and 13,761 bytes. SHA-256 matched after
  downloading the S3 object. Snapshot time: 2026-10-26T23:50:32.083439+00:00.
- Replaying the same event returned the same key and checksum with created=false.
- All four S3 public-access blocks and bucket versioning were verified enabled.
- CloudWatch contained an ingestion_success event.
- Scheduler readback confirmed ENABLED and rate(1 hour).

## Reproduce deployment in an authorized account

Use a region allowed by the account's organization. In a working copy, create a
Python 3.13 environment and install requirements-lambda.txt, then build with
`python scripts/build_lambda.py`. Copy `infra/aws/stockholm.tfvars.example` to the
ignored `infra/aws/terraform.tfvars`; fill in the target account and a unique
bucket name. Leave scheduling disabled for the first deployment.

Run Terraform init, fmt -check, validate and test from infra/aws. Review regional
costs and IAM permissions, then set deployment_authorized=true for an approved
deployment. Generate a saved plan, review all changes and apply that exact plan.
Do not apply old plan files after configuration or state changes.

CloudShell home storage is limited. If the provider exceeds available space,
set TF_DATA_DIR to a fresh directory under /tmp before init and reuse that value
for subsequent commands. Keep the working directory and terraform.tfstate in
persistent storage. Temporary provider storage can disappear when the environment
is replaced; reinstall providers rather than recreating deployed resources.

After a successful ingestion test and replay check, set schedule_enabled=true,
review a fresh plan and apply it. Expected changes are the schedule state and
freshness alarm actions. Add and confirm an SNS subscription using an authorized
recipient before relying on human alerts.

## Costs

Public Stockholm price-list rates were checked during deployment. The existing
720-runs/month model produces an approximate USD 0.71855 monthly subtotal before
credits. Keep a USD 1–3 planning allowance, not a hard spending cap. Exclusions
include taxes, growth, unusual retries/downloads and small log-retention/SQS/SNS
charges. No RDS, EC2, NAT gateway or optional API secret was created.

Reproduce with `python scripts/estimate_aws_costs.py --region eu-north-1 --refresh`.
This downloads unsigned public pricing only and does not authenticate or provision.

## Operations and recovery

Inspect Lambda logs and failure queues, and check that new objects arrive under
raw/tfl/tube/. For pausing collection, set schedule_enabled=false and apply a
reviewed plan. Disabling collection does not remove fixed monitoring charges.

Back up Terraform state privately outside this public repository. Do not lose
state: import/reconcile resources before any future apply if state is missing.
The bucket has prevent_destroy=true and force_destroy=false. Do not remove those
protections casually; object lifecycle expiry still removes old data by design.

Do not commit .env, real tfvars, state, plan files, credentials, ZIP packages or
raw snapshots. Commit source, sanitized evidence, examples and this runbook.

## Automatic-delivery fix and verification

The first automatic test exposed Unicode-escaped context tokens in Terraform's
jsonencode output. Lambda received literal placeholders and rejected the event.
Scheduler input now replaces the encoded angle brackets with literal characters
so Scheduler can substitute its context attributes. A mock-plan assertion checks
the actual encoded input; test variables explicitly disable scheduling so live
tfvars cannot change the offline test assumptions. All three mock tests passed.

The reviewed fix changed only the schedule input. Automatic collection succeeded
at 2026-10-27T00:25:25.230891Z (8:25 PM New York on 26 October), execution ID
946adfef-42a6-4637-bf8a-a8f24116bf24, with all 11 Tube lines and matching SHA-256.
The enabled hourly expression was restored and read back. Failed test messages
remain in the failure queue as diagnostic evidence; they were not purged.
