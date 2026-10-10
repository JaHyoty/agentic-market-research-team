# ECS Cluster, Task Definition, Service, and Autoscaling

variable "vpc_id" {}
variable "subnet_ids" { type = list(string) }
variable "ecr_repository_url" {}
variable "sqs_queue_url" {}
variable "sqs_queue_name" {}
variable "s3_reports_bucket" {}
variable "dynamodb_table_name" {}
variable "max_capacity" { default = 5 }
variable "region" {}
variable "environment" {}

data "aws_caller_identity" "current" {}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/market-research-worker"
  retention_in_days = 7
}

# ECS Cluster (Fargate only, no EC2)
resource "aws_ecs_cluster" "main" {
  name = "market-research"

  setting {
    name  = "containerInsights"
    value = "disabled" # Cost savings
  }
}

# Security Group for Worker Tasks
resource "aws_security_group" "worker" {
  name        = "market-research-worker"
  description = "Security group for worker ECS tasks"
  vpc_id      = var.vpc_id

  # Outbound: Allow all (needed for API calls, S3, DynamoDB, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "market-research-worker"
  }
}

# ECS Execution Role (for pulling images, writing logs)
resource "aws_iam_role" "ecs_execution" {
  name        = "market-research-ecs-execution"
  description = "Allows ECS agents to pull images and push logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Worker Task Role (for accessing AWS services)
resource "aws_iam_role" "worker" {
  name        = "market-research-worker"
  description = "Allows Worker tasks to access SQS, DynamoDB, S3"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "worker" {
  name = "market-research-worker-policy"
  role = aws_iam_role.worker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:ChangeMessageVisibility",
          "sqs:GetQueueAttributes"
        ]
        Resource = "arn:aws:sqs:${var.region}:${data.aws_caller_identity.current.account_id}:${var.sqs_queue_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = "arn:aws:dynamodb:${var.region}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_name}"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::${var.s3_reports_bucket}/*"
      },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:market-research-keys*"
      }
    ]
  })
}

# Task Definition
resource "aws_ecs_task_definition" "worker" {
  family                   = "market-research-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512  # 0.5 vCPU
  memory                   = 1024 # 1 GB
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.worker.arn

  container_definitions = jsonencode([{
    name  = "worker"
    image = "${var.ecr_repository_url}:latest"
    command = ["python", "-m", "backend.app.worker"]
    
    environment = [
      { name = "AWS_REGION", value = var.region },
      { name = "ENV", value = var.environment },
      { name = "SQS_QUEUE_URL", value = var.sqs_queue_url },
      { name = "DYNAMODB_TABLE_TASKS", value = var.dynamodb_table_name },
      { name = "S3_BUCKET_REPORTS", value = var.s3_reports_bucket },
      { name = "SECRETS_NAME", value = "market-research-keys" }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.worker.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "worker"
      }
    }
  }])
}

# ECS Service
resource "aws_ecs_service" "worker" {
  name            = "worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 0 # Scale to zero
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.subnet_ids
    security_groups = [aws_security_group.worker.id]
    assign_public_ip = true
  }

  # Allow scale-to-zero
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [desired_count] # Managed by autoscaling
  }
}

# Autoscaling Target
resource "aws_appautoscaling_target" "worker" {
  max_capacity       = var.max_capacity
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Scale based on SQS messages
resource "aws_appautoscaling_policy" "worker_scale_out" {
  name               = "worker-scale-out"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 60
    metric_aggregation_type = "Average"

    step_adjustment {
      scaling_adjustment          = 1
      metric_interval_lower_bound = 0
    }
  }
}

resource "aws_appautoscaling_policy" "worker_scale_in" {
  name               = "worker-scale-in"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "PercentChangeInCapacity"
    cooldown                = 300
    metric_aggregation_type = "Average"

    step_adjustment {
      scaling_adjustment          = -100
      metric_interval_upper_bound = 0
    }
  }
}

# CloudWatch Alarm for Scale Out (messages in queue > 0)
resource "aws_cloudwatch_metric_alarm" "sqs_messages_high" {
  alarm_name          = "market-research-sqs-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Average"
  threshold           = 0
  alarm_description   = "Scale out when messages in queue"
  
  dimensions = {
    QueueName = var.sqs_queue_name
  }

  alarm_actions = [aws_appautoscaling_policy.worker_scale_out.arn]
}

# CloudWatch Alarm for Scale In (messages in queue = 0)
resource "aws_cloudwatch_metric_alarm" "sqs_messages_low" {
  alarm_name          = "market-research-sqs-low"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 0
  alarm_description   = "Scale in when queue empty and no tasks in flight"

  metric_query {
    id          = "e1"
    expression  = "visible + not_visible"
    label       = "TotalMessages"
    return_data = true
  }

  metric_query {
    id = "visible"
    metric {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      period      = 60
      stat        = "Average"
      dimensions = {
        QueueName = var.sqs_queue_name
      }
    }
  }

  metric_query {
    id = "not_visible"
    metric {
      metric_name = "ApproximateNumberOfMessagesNotVisible"
      namespace   = "AWS/SQS"
      period      = 60
      stat        = "Average"
      dimensions = {
        QueueName = var.sqs_queue_name
      }
    }
  }

  alarm_actions = [aws_appautoscaling_policy.worker_scale_in.arn]
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "service_name" {
  value = aws_ecs_service.worker.name
}
