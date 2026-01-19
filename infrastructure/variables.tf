variable "region" {
  default = "us-east-1"
}

variable "ecs_max_capacity" {
  default = 5
}


variable "openrouter_api_key" {
  description = "API Key for OpenRouter"
  type        = string
  sensitive   = true
}

variable "tavily_api_key" {
  description = "API Key for Tavily"
  type        = string
  sensitive   = true
}

variable "environment" {
  default = "prod"
}
