variable "sqs_queue_url" {}
variable "dynamodb_table_name" {}
variable "dynamodb_table_arn" {}
variable "sqs_queue_arn" {}
variable "s3_reports_bucket" { default = "" }
variable "s3_reports_bucket_arn" { default = "" }
variable "ecs_cluster_name" { default = "" }
variable "ecs_service_name" { default = "" }
variable "environment" {}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../../backend/lambdas/handler.py"
  output_path = "${path.module}/lambda_function.zip"
}

# --- Submit Handler (POST /research) ---

resource "aws_lambda_function" "submit_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "market-research-submit-handler"
  description      = "Handles POST /research to submit tasks to SQS"
  role             = aws_iam_role.submit_role.arn
  handler          = "handler.submit_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10

  environment {
    variables = {
      SQS_QUEUE_URL        = var.sqs_queue_url
      DYNAMODB_TABLE_TASKS = var.dynamodb_table_name
      ECS_CLUSTER_NAME     = var.ecs_cluster_name
      ECS_SERVICE_NAME     = var.ecs_service_name
      ENV                  = var.environment
    }
  }
}

resource "aws_iam_role" "submit_role" {
  name        = "market_research_submit_lambda_role"
  description = "IAM Role for Submit Lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "submit_policy" {
  name = "market_research_submit_policy"
  role = aws_iam_role.submit_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = var.sqs_queue_arn
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arn
      },
      {
        Effect = "Allow"
        Action = ["ecs:DescribeServices", "ecs:UpdateService"]
        Resource = "*"
      }
    ]
  })
}

# --- Get Status Handler (GET /tasks/{task_id}) ---

resource "aws_lambda_function" "get_status_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "market-research-get-status-handler"
  description      = "Handles GET /tasks/{id} to check status"
  role             = aws_iam_role.get_status_role.arn
  handler          = "handler.get_status_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 5

  environment {
    variables = {
      DYNAMODB_TABLE_TASKS = var.dynamodb_table_name
    }
  }
}

resource "aws_iam_role" "get_status_role" {
  name        = "market_research_get_status_lambda_role"
  description = "IAM Role for Get Status Lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "get_status_policy" {
  name = "market_research_get_status_policy"
  role = aws_iam_role.get_status_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:GetItem"]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# --- Get Sessions Handler (GET /sessions) ---

resource "aws_lambda_function" "get_sessions_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "market-research-get-sessions-handler"
  description      = "Handles GET /sessions to list research sessions"
  role             = aws_iam_role.get_sessions_role.arn
  handler          = "handler.get_sessions_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10

  environment {
    variables = {
      DYNAMODB_TABLE_TASKS = var.dynamodb_table_name
    }
  }
}

resource "aws_iam_role" "get_sessions_role" {
  name        = "market_research_get_sessions_lambda_role"
  description = "IAM Role for Get Sessions Lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "get_sessions_policy" {
  name = "market_research_get_sessions_policy"
  role = aws_iam_role.get_sessions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["dynamodb:Scan"]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# --- Get Report Handler (GET /reports/{task_id}) ---

resource "aws_lambda_function" "get_report_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "market-research-get-report-handler"
  description      = "Handles GET /reports/{id} to retrieve PDF"
  role             = aws_iam_role.get_report_role.arn
  handler          = "handler.get_report_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10

  environment {
    variables = {
      DYNAMODB_TABLE_TASKS = var.dynamodb_table_name
      S3_BUCKET_REPORTS    = var.s3_reports_bucket
    }
  }
}

resource "aws_iam_role" "get_report_role" {
  name        = "market_research_get_report_lambda_role"
  description = "IAM Role for Get Report Lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "get_report_policy" {
  name = "market_research_get_report_policy"
  role = aws_iam_role.get_report_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = var.s3_reports_bucket_arn != "" ? "${var.s3_reports_bucket_arn}/*" : "arn:aws:s3:::market-research-reports-*/*"
      }
    ]
  })
}

# --- Outputs ---

output "submit_function_name" {
  value = aws_lambda_function.submit_handler.function_name
}

output "submit_invoke_arn" {
  value = aws_lambda_function.submit_handler.invoke_arn
}

output "get_status_function_name" {
  value = aws_lambda_function.get_status_handler.function_name
}

output "get_status_invoke_arn" {
  value = aws_lambda_function.get_status_handler.invoke_arn
}

output "get_sessions_function_name" {
  value = aws_lambda_function.get_sessions_handler.function_name
}

output "get_sessions_invoke_arn" {
  value = aws_lambda_function.get_sessions_handler.invoke_arn
}

output "get_report_function_name" {
  value = aws_lambda_function.get_report_handler.function_name
}

output "get_report_invoke_arn" {
  value = aws_lambda_function.get_report_handler.invoke_arn
}
