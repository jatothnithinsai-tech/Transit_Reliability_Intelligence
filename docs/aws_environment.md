# AWS environment and secure configuration

Current discovery: Python 3.13.7 and Boto3 1.43.111 are available. Terraform 1.13.5 is installed locally under `.tools/terraform-1.13.5/`; its signed AWS provider 6.69.1 is already installed and locked. AWS CLI is not on PATH or in the checked standard installation location. No usable default SDK credentials, named AWS profiles or configured default region were found. No AWS account identity or billing eligibility could be verified, and no login was attempted. See [environment evidence](validation/aws_environment.json).

Terraform's proposed target region is `eu-west-2` (London). That is a proposal, not evidence of a configured or authenticated AWS account. The account ID in `terraform.tfvars.example` is deliberately a placeholder. An authenticated short-lived profile, approved account ID, globally unique bucket name and explicit cost approval are prerequisites for a real plan or deployment. AWS CLI is optional for Terraform/Boto3, but commands using `aws` in the operating guide require it to be installed later.

| Setting | Normal local ETL | Future Lambda |
|---|---|---|
| S3_ENABLED | false | true, supplied by Terraform |
| S3_MODE | local | aws |
| S3_ALLOW_AWS | false | true, supplied by approved infrastructure |
| S3_ENDPOINT_URL | loopback emulator only | ignored; standard AWS endpoint |
| S3_BUCKET / S3_PREFIX | local emulator bucket / raw/tfl/tube | defined private bucket / raw/tfl/tube |
| AWS_REGION | eu-west-2 example only | AWS Lambda's supplied region |
| PIPELINE_NAME | unused | fixed function name; metric dimension |
| EXPECTED_SCHEDULE_ARN | unused | defined Scheduler ARN, assembled without a dependency cycle |
| TFL_SECRET_ARN | unused | empty by default, or the one optional Secrets Manager ARN |

Local `.env` is read only by local entry points, never packaged for Lambda. Database passwords remain local. A TfL app key is optional for the endpoint used here; the no-key public endpoint has not been live-tested in AWS. If a key is required, the optional Secrets Manager resource stores only a placeholder definition. Populate its JSON `TFL_API_KEY` value separately after an approved deployment. No secret-value Terraform resource is used, so the value is not placed in Terraform state by this configuration. The secret's managed AWS encryption avoids an unnecessary paid customer-managed key.

Use short-lived SSO/role credentials in a future approved account. Never paste access keys into the chat, source, tfvars, screenshots or deployment ZIP. The runtime obtains its identity from its IAM role. Do not grant the deployment identity broad permissions to existing unrelated resources; it must be able to provision the reviewed stack and pass only the Lambda/Scheduler roles to their respective services. A real plan must be reviewed for unexpected updates, replacements or deletions before approval to apply.

Default deployment authorization and scheduling both remain false. The bucket resource precondition rejects an unapproved real deployment plan. Mock tests override that variable only inside a mocked provider; they do not configure a live AWS provider or create resources.
