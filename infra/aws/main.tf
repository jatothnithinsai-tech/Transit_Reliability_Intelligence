locals {
  function_name = "${var.name}-ingestion"
  object_prefix = "raw/tfl/tube"
  lambda_zip    = "${path.module}/dist/lambda.zip"
}
resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
}
resource "aws_secretsmanager_secret" "tfl" {
  count                   = var.use_api_secret ? 1 : 0
  name                    = "${var.name}/tfl-api"
  recovery_window_in_days = 7
  description             = "JSON containing TFL_API_KEY; value is managed outside Terraform/state."
}
resource "aws_iam_role" "lambda" {
  name = "${var.name}-lambda"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy" "lambda" {
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Effect   = "Allow", Action = ["s3:PutObject", "s3:GetObject"]
        Resource = ["${aws_s3_bucket.raw.arn}/${local.object_prefix}/*", "${aws_s3_bucket.raw.arn}/control/tfl/tube/runs/*"]
      },
      {
        Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.ingestion.arn}:*"
      },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.failed_invocations.arn }
      ], var.use_api_secret ? [{
        Effect   = "Allow", Action = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.tfl[0].arn
    }] : [])
  })
}
resource "aws_lambda_function" "ingestion" {
  function_name                  = local.function_name
  role                           = aws_iam_role.lambda.arn
  runtime                        = "python3.13"
  architectures                  = ["x86_64"]
  handler                        = "src.cloud.lambda_handler.handler"
  filename                       = local.lambda_zip
  source_code_hash               = filebase64sha256(local.lambda_zip)
  timeout                        = 120
  memory_size                    = 128
  reserved_concurrent_executions = 1
  publish                        = true
  environment {
    variables = {
      S3_ENABLED            = "true", S3_MODE = "aws", S3_ALLOW_AWS = "true"
      S3_BUCKET             = aws_s3_bucket.raw.id, S3_PREFIX = local.object_prefix
      TFL_SECRET_ARN        = var.use_api_secret ? aws_secretsmanager_secret.tfl[0].arn : ""
      PIPELINE_NAME         = local.function_name
      EXPECTED_SCHEDULE_ARN = "arn:aws:scheduler:${var.region}:${var.aws_account_id}:schedule/${aws_scheduler_schedule_group.ingestion.name}/${var.name}-hourly"
    }
  }
  depends_on = [aws_iam_role_policy.lambda, aws_s3_bucket_public_access_block.raw,
    aws_s3_bucket_policy.raw, aws_s3_bucket_server_side_encryption_configuration.raw,
  aws_s3_bucket_versioning.raw]
}
resource "aws_lambda_function_event_invoke_config" "ingestion" {
  function_name                = aws_lambda_function.ingestion.function_name
  maximum_event_age_in_seconds = 3600
  maximum_retry_attempts       = 2
  destination_config {
    on_failure { destination = aws_sqs_queue.failed_invocations.arn }
  }
}
