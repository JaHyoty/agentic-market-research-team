provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = "agentic-market-research"
      Environment = var.environment
    }
  }
}

# CloudFront certificates must live in us-east-1
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Required for CloudFront OAC
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

module "vpc" {
  source = "./vpc"
  region = var.region
}

module "sqs" {
  source     = "./sqs"
  queue_name = "market-research-tasks"
}

module "s3" {
  source        = "./s3"
  bucket_prefix = "market-research"
}

module "dynamodb" {
  source     = "./dynamodb"
  table_name = "market-research-tasks"
}

module "ecr" {
  source = "./ecr"
}

module "lambda" {
  source                = "./lambda"
  sqs_queue_url         = module.sqs.queue_url
  sqs_queue_arn         = module.sqs.queue_arn
  dynamodb_table_name   = module.dynamodb.table_name
  dynamodb_table_arn    = module.dynamodb.table_arn
  s3_reports_bucket     = module.s3.reports_bucket
  s3_reports_bucket_arn = module.s3.reports_bucket_arn
  ecs_cluster_name      = module.ecs.cluster_name
  ecs_service_name      = module.ecs.service_name
  environment           = var.environment
}

module "apigateway" {
  source    = "./apigateway"
  region    = var.region
  sqs_queue_url = module.sqs.queue_url
  sqs_queue_arn = module.sqs.queue_arn

  # Lambda Integrations
  submit_lambda_invoke_arn        = module.lambda.submit_invoke_arn
  submit_lambda_function_name     = module.lambda.submit_function_name
  get_status_lambda_invoke_arn    = module.lambda.get_status_invoke_arn
  get_status_lambda_function_name = module.lambda.get_status_function_name
  get_sessions_lambda_invoke_arn    = module.lambda.get_sessions_invoke_arn
  get_sessions_lambda_function_name = module.lambda.get_sessions_function_name
  get_report_lambda_invoke_arn    = module.lambda.get_report_invoke_arn
  get_report_lambda_function_name = module.lambda.get_report_function_name
}

module "ecs" {
  source              = "./ecs"
  vpc_id              = module.vpc.vpc_id
  subnet_ids          = module.vpc.public_subnets
  ecr_repository_url  = module.ecr.repository_url
  sqs_queue_url       = module.sqs.queue_url
  sqs_queue_name      = module.sqs.queue_name
  s3_reports_bucket   = module.s3.reports_bucket
  dynamodb_table_name = module.dynamodb.table_name
  max_capacity        = var.ecs_max_capacity
  region              = var.region
  environment         = var.environment
}

module "cloudfront" {
  source         = "./cloudfront"
  api_endpoint   = module.apigateway.api_endpoint
  primary_domain = var.primary_domain
  domains        = var.domains

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}

# Outputs
output "api_endpoint" {
  value = module.apigateway.api_endpoint
}

output "cloudfront_url" {
  value = module.cloudfront.cloudfront_url
}

output "site_url" {
  value = module.cloudfront.site_url
}

output "cloudfront_distribution_id" {
  value = module.cloudfront.cloudfront_distribution_id
}

output "frontend_bucket" {
  value = module.cloudfront.frontend_bucket
}

output "ecr_repository_url" {
  value = module.ecr.repository_url
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_service_name" {
  value = module.ecs.service_name
}
