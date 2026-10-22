# AWS deployment and rollback plan — NOT DEPLOYED

This is the current plan for the requested **EventBridge Scheduler → Lambda → TfL → private S3** architecture. It supersedes the earlier un-deployed EventBridge-rule design. No resources have been created, modified or deleted in AWS.

Read the [architecture](aws_architecture.md), [environment](aws_environment.md), [operating guide](aws_operations.md), [London cost proposal](aws_costs.md), and [local integration notes](aws_local_integration.md). The original local PostgreSQL and Power BI system remains independent.

## Proposed resources

Default prefix: `transit-reliability`; region: `eu-west-2`; bucket name proposed as `transit-reliability-ACCOUNT_ID-eu-west-2-raw` after account identity is known.

| Terraform resource(s) | Count | Purpose |
|---|---:|---|
| aws_s3_bucket.raw | 1 | Private raw snapshots and execution manifests |
| Bucket public access block, ownership, versioning, encryption, lifecycle and policy | 6 | Public-access prevention, AES256, TLS, retention and versioning |
| aws_lambda_function.ingestion | 1 | Python 3.13/x86_64, 128 MB, 120-second timeout, concurrency 1 |
| aws_lambda_function_event_invoke_config.ingestion | 1 | Async retries/event age and execution-failure destination |
| aws_scheduler_schedule_group.ingestion | 1 | Dedicated Scheduler group and trust boundary |
| aws_scheduler_schedule.hourly | 1 | Hourly schedule, disabled by default, context-aware input |
| Lambda and Scheduler IAM roles | 2 | Separate service identities |
| Lambda and Scheduler inline policies | 2 | Scoped permissions; no administrative wildcard allows |
| CloudWatch log group | 1 | 14-day retention |
| Four CloudWatch alarms | 4 | Errors, missing successful uploads, and each DLQ |
| SQS delivery/execution failure queues | 2 | Encrypted, seven-day retention |
| SNS alert topic | 1 | Notification destination; subscriber not configured |
| **Total default Terraform-managed objects** | **23** | No RDS, EC2, NAT, DynamoDB or custom KMS key |

One optional Secrets Manager secret increases the total to **24** if explicitly approved. No secret value is created by Terraform. The runtime emits one custom CloudWatch metric via logs; that is a billable usage item, not a separate Terraform resource. Subscriber/billing-alert setup is outside this default list.

The [machine-readable resource proposal](validation/proposed_resources.json) was produced by a **mocked plan**, not an AWS account-backed plan. It lists 23 create actions against generated mock values. It cannot establish that names are available or that no unrelated resources exist in a real account.

## Work completed before approval

- Shared TfL client with bounded cloud HTTP retries/timeouts and API structure validation.
- Snapshot upload/readback integrity, capture-time and source/execution lineage.
- Conditional S3 execution leases, completed-run replay, failed-run recovery and bounded raw/control retention.
- Scheduler execution role with account/group trust constraints, one Lambda invocation target and one delivery DLQ.
- CloudWatch structured logs, one upload metric and four alarms.
- Locked portable Lambda dependencies and a real generated deployment ZIP.
- Python tests, isolated package imports, Terraform formatting/schema validation and mocked plan assertions.
- Public London price-list calculation: approximately US$0.72/month before exclusions; propose US$1–$3/month as planning allowance, with zero Free Tier deductions.

No AWS credentials, profiles or default region are configured in the current environment. AWS CLI is unavailable, although Boto3 and local Terraform work. Thus STS identity, actual account eligibility, service quotas, a real plan and actual Lambda/Linux execution are blocked or unperformed. These are not claimed to be verified by Moto or Terraform mocks.

## Future deployment prerequisites

1. Obtain explicit approval for the target account/profile, region, 23-resource list and nonzero cost estimate. Keep `deployment_authorized=false` until then.
2. Use an existing authenticated short-lived AWS profile; never provide access keys in chat or files. Resolve the account ID read-only and verify available Lambda regional concurrency can support reservation 1 while respecting the unreserved-concurrency requirement.
3. Select an available private bucket name. Confirm there is no unexpected existing Terraform state/backend or resource collision. Use encrypted, access-controlled state and approved deployment permissions; this template does not create a remote state backend.
4. Rebuild the ZIP from the locked Python 3.13 environment and review `infra/aws/dist/build_manifest.json` plus `docs/validation/lambda_package.json`. Rebuild after any source change. The ZIP remains ignored rather than committed.
5. Fill an ignored tfvars file from `terraform.tfvars.example`. The real account ID and bucket name must replace placeholders. Leave scheduling disabled for the initial deployment.

## Commands and checks

Available offline commands, already exercised:

```powershell
.\.venv\Scripts\python.exe scripts/run_checks.py
.\.venv\Scripts\python.exe scripts/build_lambda.py --installed
.\.tools\terraform-1.13.5\terraform.exe -chdir=infra/aws fmt -check -recursive
.\.tools\terraform-1.13.5\terraform.exe -chdir=infra/aws validate
.\.tools\terraform-1.13.5\terraform.exe -chdir=infra/aws test
```

Terraform 1.13.5 uses the existing signed AWS provider 6.69.1. Mock tests use plan-only runs; no real provider authentication, apply or AWS teardown occurs. They check the hourly disabled schedule, context fields, public-access/encryption controls, IAM scope/trust, bounded runtime/logs, optional secret references, and rejection without approval. [HashiCorp provider-mocking documentation](https://developer.hashicorp.com/terraform/language/tests/mocking).

In a separately approved future deployment context, initialize providers if necessary, then generate an account-backed plan using the approved variables. A real plan may contact AWS. Inspect its exact account, region, names, permissions, quantities and charges; stop if it proposes modifying/deleting existing resources outside the explicit approval. No real plan or apply was run in this completion session.

After a separately approved apply, populate the optional secret out of band if enabled. Test one authorized Scheduler-compatible invocation and inspect its snapshot, checksum, manifest, logs and metric. Test delivery/handler failures only against approved test objects. Enable scheduling only after these checks and a fresh cost review. Configure an SNS subscriber only if separately approved; the topic alone delivers no user notification.

## Rollback and teardown

These are future procedures, not actions authorized or performed now:

1. Disable the approved Scheduler schedule before changing code; inspect in-flight executions, both queues and logs. Do not assume disabling scheduling cancels already accepted async invocations.
2. Restore a previously reviewed ZIP/source release and configuration with scheduling off. This template publishes versions but does not provide an automated alias/traffic-shift rollback. Retain release ZIPs/hashes locally when managing a real deployment.
3. Preserve raw objects, execution manifests and failure evidence. Bucket prevent_destroy and force_destroy=false intentionally block routine destructive teardown. Object/version deletion or changing that protection requires explicit approval and a verified retention/export decision.
4. After a separately authorized cleanup decision, review the teardown plan for the listed stack objects only. Do not delete pre-existing unrelated resources. Secrets use a seven-day recovery window. Logs, secrets, alarm definitions, Lambda versions and retained object versions may continue to cost money after scheduling is stopped.
5. Confirm both current and noncurrent object/version retention and any pending secret deletion before considering the future account cleanup complete. No bulk-delete or automated destroy command is included in the execution workflow.

## Single next approval

Approve the **23-resource eu-west-2 proposal and US$1–$3/month planning allowance**, and identify the authenticated AWS profile/target account to use. The optional secret/subscriber are excluded unless separately selected. That approval would permit the next account identity/quota checks and real plan; it is not evidence that deployment has already happened.