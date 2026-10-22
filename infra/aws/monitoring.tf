resource "aws_sqs_queue" "delivery_failures" {
  name                      = "${var.name}-delivery-failures"
  message_retention_seconds = 604800
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "failed_invocations" {
  name                      = "${var.name}-failed-invocations"
  message_retention_seconds = 604800
  sqs_managed_sse_enabled   = true
}
resource "aws_sns_topic" "alerts" { name = "${var.name}-alerts" }
resource "aws_cloudwatch_metric_alarm" "errors" {
  alarm_name          = "${var.name}-lambda-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions          = { FunctionName = aws_lambda_function.ingestion.function_name }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "missing_invocations" {
  alarm_name          = "${var.name}-missing-snapshots"
  namespace           = "TransitReliability"
  metric_name         = "SnapshotsUploaded"
  statistic           = "Sum"
  period              = 7200
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  dimensions          = { PipelineName = local.function_name }
  actions_enabled     = var.schedule_enabled
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
resource "aws_cloudwatch_metric_alarm" "dead_letters" {
  for_each            = { delivery = aws_sqs_queue.delivery_failures.name, execution = aws_sqs_queue.failed_invocations.name }
  alarm_name          = "${var.name}-${each.key}-dead-letters"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = each.value }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
