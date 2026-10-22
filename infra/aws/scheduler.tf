resource "aws_scheduler_schedule_group" "ingestion" {
  name = var.name
}
resource "aws_iam_role" "scheduler" {
  name = "${var.name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole"
      Principal = { Service = "scheduler.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = var.aws_account_id }
        ArnEquals    = { "aws:SourceArn" = aws_scheduler_schedule_group.ingestion.arn }
      }
    }]
  })
}
resource "aws_iam_role_policy" "scheduler" {
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = aws_lambda_function.ingestion.arn },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = aws_sqs_queue.delivery_failures.arn }
    ]
  })
}
resource "aws_scheduler_schedule" "hourly" {
  name                         = "${var.name}-hourly"
  group_name                   = aws_scheduler_schedule_group.ingestion.name
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "UTC"
  state                        = var.schedule_enabled ? "ENABLED" : "DISABLED"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_lambda_function.ingestion.arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      scheduled_time = "<aws.scheduler.scheduled-time>"
      execution_id   = "<aws.scheduler.execution-id>"
      schedule_arn   = "<aws.scheduler.schedule-arn>"
      attempt_number = "<aws.scheduler.attempt-number>"
    })
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
    dead_letter_config { arn = aws_sqs_queue.delivery_failures.arn }
  }
  depends_on = [aws_iam_role_policy.scheduler, aws_lambda_function_event_invoke_config.ingestion]
}
