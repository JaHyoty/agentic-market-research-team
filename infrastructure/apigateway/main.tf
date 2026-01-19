variable "sqs_queue_url" {}
variable "sqs_queue_arn" {}
variable "region" {}
variable "submit_lambda_invoke_arn" {}
variable "submit_lambda_function_name" {}
variable "get_status_lambda_invoke_arn" {}
variable "get_status_lambda_function_name" {}
variable "get_sessions_lambda_invoke_arn" {}
variable "get_sessions_lambda_function_name" {}
variable "get_report_lambda_invoke_arn" {}
variable "get_report_lambda_function_name" {}

resource "aws_apigatewayv2_api" "api" {
  name          = "market-research-api"
  description   = "Market Research API for managing tasks and reports"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*", "X-Browser-Session-Id"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  description = "Default stage"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 10 # 10/second for general endpoints
  }

  route_settings {
    route_key              = "POST /api/research"
    throttling_burst_limit = 2
    throttling_rate_limit  = 2 # 2/second for research (prevents abuse)
  }

  depends_on = [
    aws_apigatewayv2_route.post_research,
    aws_apigatewayv2_route.get_task,
    aws_apigatewayv2_route.get_sessions,
    aws_apigatewayv2_route.get_report
  ]
}

# --- POST /research -> Submit Lambda ---

resource "aws_apigatewayv2_integration" "submit_integration" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = var.submit_lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_research" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /api/research"
  target    = "integrations/${aws_apigatewayv2_integration.submit_integration.id}"
}

resource "aws_lambda_permission" "apigw_submit_lambda" {
  statement_id  = "AllowExecutionFromAPIGatewaySubmit"
  action        = "lambda:InvokeFunction"
  function_name = var.submit_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*/api/research"
}

# --- GET /tasks/{task_id} -> Get Status Lambda ---

resource "aws_apigatewayv2_integration" "get_status_integration" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = var.get_status_lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_task" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /api/tasks/{task_id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_status_integration.id}"
}

resource "aws_lambda_permission" "apigw_get_status_lambda" {
  statement_id  = "AllowExecutionFromAPIGatewayGetStatus"
  action        = "lambda:InvokeFunction"
  function_name = var.get_status_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*/api/tasks/*"
}

# --- GET /sessions -> Get Sessions Lambda ---

resource "aws_apigatewayv2_integration" "get_sessions_integration" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = var.get_sessions_lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_sessions" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /api/sessions"
  target    = "integrations/${aws_apigatewayv2_integration.get_sessions_integration.id}"
}

resource "aws_lambda_permission" "apigw_get_sessions_lambda" {
  statement_id  = "AllowExecutionFromAPIGatewayGetSessions"
  action        = "lambda:InvokeFunction"
  function_name = var.get_sessions_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*/api/sessions"
}

# --- GET /reports/{task_id} -> Get Report Lambda ---

resource "aws_apigatewayv2_integration" "get_report_integration" {
  api_id             = aws_apigatewayv2_api.api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = var.get_report_lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_report" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /api/reports/{task_id}"
  target    = "integrations/${aws_apigatewayv2_integration.get_report_integration.id}"
}

resource "aws_lambda_permission" "apigw_get_report_lambda" {
  statement_id  = "AllowExecutionFromAPIGatewayGetReport"
  action        = "lambda:InvokeFunction"
  function_name = var.get_report_lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*/api/reports/*"
}

# --- Outputs ---

output "api_endpoint" {
  value = aws_apigatewayv2_api.api.api_endpoint
}

output "api_id" {
  value = aws_apigatewayv2_api.api.id
}
