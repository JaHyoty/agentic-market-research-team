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

variable "primary_domain" {
  description = "Canonical site hostname"
  default     = "market-research.jahyoty.com"
}

variable "domains" {
  description = "Hostname => Route53 hosted zone. Non-primary hostnames 301-redirect to primary_domain."
  type        = map(string)
  default = {
    "market-research.jahyoty.com"     = "jahyoty.com"
    "market-research.jaakkohyoty.com" = "jaakkohyoty.com"
  }
}
