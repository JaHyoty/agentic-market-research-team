variable "queue_name" {}

resource "aws_sqs_queue" "tasks" {
  name                       = var.queue_name
  visibility_timeout_seconds = 60    # Worker heartbeat extends this
  message_retention_seconds  = 86400 # 1 day
}

output "queue_url" {
  value = aws_sqs_queue.tasks.id
}

output "queue_arn" {
  value = aws_sqs_queue.tasks.arn
}

output "queue_name" {
  value = aws_sqs_queue.tasks.name
}
