mock_provider "aws" {
  override_during = plan
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::000000000000:role/offline-test" }
  }
  mock_resource "aws_lambda_function" {
    defaults = { arn = "arn:aws:lambda:eu-west-2:000000000000:function:transit-reliability-ingestion" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::transit-offline-validation", id = "transit-offline-validation" }
  }
  mock_resource "aws_sqs_queue" {
    defaults = { arn = "arn:aws:sqs:eu-west-2:000000000000:offline-failures" }
  }
  mock_resource "aws_scheduler_schedule_group" {
    defaults = { arn = "arn:aws:scheduler:eu-west-2:000000000000:schedule-group/transit-reliability" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:eu-west-2:000000000000:log-group:/aws/lambda/transit-reliability-ingestion" }
  }
  mock_resource "aws_sns_topic" {
    defaults = { arn = "arn:aws:sns:eu-west-2:000000000000:offline-alerts" }
  }
  mock_resource "aws_secretsmanager_secret" {
    defaults = { arn = "arn:aws:secretsmanager:eu-west-2:000000000000:secret:transit-test-123456" }
  }
}

variables {
  aws_account_id = "000000000000"
  bucket_name    = "transit-offline-validation"
  # Mock-only authorization permits evaluation; real defaults remain false.
  deployment_authorized = true
}

run "secure_hourly_architecture" {
  command = plan
  assert {
    condition     = aws_scheduler_schedule.hourly.state == "DISABLED" && aws_scheduler_schedule.hourly.schedule_expression == "rate(1 hour)"
    error_message = "Hourly Scheduler must be disabled until approved."
  }
  assert {
    condition     = aws_scheduler_schedule.hourly.flexible_time_window[0].mode == "OFF"
    error_message = "Flexible execution windows must be disabled."
  }
  assert {
    condition     = jsondecode(aws_scheduler_schedule.hourly.target[0].input).scheduled_time == "<aws.scheduler.scheduled-time>"
    error_message = "Scheduler must send stable scheduled-time context."
  }
  assert {
    condition     = aws_s3_bucket_public_access_block.raw.block_public_acls && aws_s3_bucket_public_access_block.raw.block_public_policy && aws_s3_bucket_public_access_block.raw.ignore_public_acls && aws_s3_bucket_public_access_block.raw.restrict_public_buckets
    error_message = "All S3 public access protections must be enabled."
  }
  assert {
    condition     = one(one(aws_s3_bucket_server_side_encryption_configuration.raw.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    error_message = "Snapshots require server-side encryption."
  }
  assert {
    condition     = aws_lambda_function.ingestion.timeout == 120 && aws_lambda_function.ingestion.reserved_concurrent_executions == 1 && aws_cloudwatch_log_group.ingestion.retention_in_days == 14
    error_message = "Bounded runtime/concurrency/log retention must be preserved."
  }
  assert {
    condition     = jsondecode(aws_iam_role.scheduler.assume_role_policy).Statement[0].Principal.Service == "scheduler.amazonaws.com"
    error_message = "Only Scheduler may assume its execution role."
  }
  assert {
    condition     = jsondecode(aws_iam_role.scheduler.assume_role_policy).Statement[0].Condition.ArnEquals["aws:SourceArn"] == aws_scheduler_schedule_group.ingestion.arn && jsondecode(aws_iam_role.scheduler.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == var.aws_account_id
    error_message = "Scheduler trust must be limited to the reviewed account and schedule group."
  }
  assert {
    condition     = toset(jsondecode(aws_iam_role_policy.lambda.policy).Statement[0].Action) == toset(["s3:PutObject", "s3:GetObject"]) && length(jsondecode(aws_iam_role_policy.lambda.policy).Statement[0].Resource) == 2
    error_message = "Lambda S3 permissions must allow only reads/writes of raw snapshots and execution manifests."
  }
  assert {
    condition     = length(aws_secretsmanager_secret.tfl) == 0 && aws_lambda_function.ingestion.environment[0].variables.TFL_SECRET_ARN == ""
    error_message = "No paid API secret should be created by default."
  }
  assert {
    condition     = aws_cloudwatch_metric_alarm.missing_invocations.metric_name == "SnapshotsUploaded" && !aws_cloudwatch_metric_alarm.missing_invocations.actions_enabled
    error_message = "Freshness must measure successful uploads, with alarm actions disabled while unscheduled."
  }
}

run "deployment_requires_approval" {
  command = plan
  variables { deployment_authorized = false }
  expect_failures = [aws_s3_bucket.raw]
}

run "optional_secret_is_referenced" {
  command = plan
  variables { use_api_secret = true }
  assert {
    condition     = length(aws_secretsmanager_secret.tfl) == 1 && aws_lambda_function.ingestion.environment[0].variables.TFL_SECRET_ARN == aws_secretsmanager_secret.tfl[0].arn
    error_message = "Optional secret references must point to a defined secret."
  }
}
