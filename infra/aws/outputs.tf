output "raw_bucket" { value = aws_s3_bucket.raw.id }
output "lambda_name" { value = aws_lambda_function.ingestion.function_name }
output "alert_topic_arn" { value = aws_sns_topic.alerts.arn }
output "api_secret_arn" { value = var.use_api_secret ? aws_secretsmanager_secret.tfl[0].arn : null }
output "schedule_name" { value = aws_scheduler_schedule.hourly.name }
output "schedule_group_name" { value = aws_scheduler_schedule_group.ingestion.name }
output "schedule_arn" { value = aws_scheduler_schedule.hourly.arn }
