# AWS cost proposal — approval required

Proposed region: **eu-west-2, London**. No resources are deployed and no AWS service charges have been incurred by this work. The prior £0 constraint remains in force until the user approves a resource list, region and nonzero budget.

The public London price lists were downloaded without credentials on 22 October 2026. The [calculation artifact](validation/aws_cost_estimate.json) records exact SKUs, regional rates, source URLs, publication dates, assumptions and exclusions. `scripts/estimate_aws_costs.py` reproduces the calculation offline from the ignored cache; `--refresh` retrieves public unsigned price-list files. No billing/account API or paid AWS resource is involved.

| Driver | Assumption | Approximate monthly USD |
|---|---|---:|
| CloudWatch alarms | Four standard alarms at $0.10 | 0.40 |
| One upload success metric | One fixed metric/dimension combination at $0.30 | 0.30 |
| Logs ingestion | 5 MiB at London $0.5985/GB | 0.0029 |
| Lambda compute and requests | 720 × 2 seconds × 128 MB; $0.0000166667/GB-second and $0.20/million requests | 0.0031 |
| S3 Standard storage | About 0.042 GB steady state, including small control manifests, at $0.024/GB-month | 0.0010 |
| S3 requests | Three PUT and one GET per ordinary successful run; London $0.0053/1,000 PUT and $0.0042/10,000 GET | 0.0118 |
| Scheduler, gross reference rate | 720 calls at the official $1/million example rate; no allowance deducted | 0.00072 |
| **Calculated subtotal** | Before listed exclusions | **0.7195** |

Allow **US$1–$3/month** for this small workload, without deducting Free Tier or credits. This allowance is not a hard cap or guarantee. It excludes tax/currency conversion, growth, unexpected retries or downloads, small log retention/SQS/SNS usage and optional Secrets Manager. If enabled, the one secret adds approximately $0.40/month plus reads at the public example rates. CloudWatch's fixed monitoring charges dominate this workload, even when scheduling is disabled after deployment.

The model uses a 30-day month, 20 KiB per snapshot, 90-day raw retention, seven-day control retention, 14-day logs, 128 MB memory and a two-second average function duration. The 120-second timeout is a limit, not the assumed mean duration. Sustained errors can produce up to three Scheduler deliveries and separate Lambda execution retries; those retries can increase duration, request and logging charges. Published Lambda versions and noncurrent S3 versions also need retention review.

No credentials or named profiles are available, so account identity, credit balance, Free Tier enrollment, existing organization-wide usage and applicable unused benefits could not be verified. Earlier user context states that usable Free Tier benefits should not be relied on. AWS's Scheduler pricing page advertises a monthly allowance, but its remaining availability in this account is unknown. The proposal therefore deducts **zero** benefits. Do not call this architecture free.

Primary sources: regional [CloudWatch price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/eu-west-2/index.json), [Lambda price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/eu-west-2/index.json), [S3 price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/eu-west-2/index.json), and public [Scheduler pricing](https://aws.amazon.com/eventbridge/pricing/), [Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/), [SQS pricing](https://aws.amazon.com/sqs/pricing/), [SNS pricing](https://aws.amazon.com/sns/pricing/).

Safeguards: disabled initial scheduling; explicit deployment precondition; target-account allowlist; reserved concurrency 1; bounded retries and event age; raw/control/log/DLQ retention; no RDS, EC2, NAT gateway, DynamoDB or paid customer-managed KMS key. Billing alerts require separate approved setup and are advisory rather than a spending limit. The only reliable way to keep this project's AWS bill at £0 is to leave it undeployed.
