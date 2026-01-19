resource "aws_secretsmanager_secret" "keys" {
  name        = "market-research-keys"
  description = "API Keys for Market Research Agent (OpenRouter, Tavily)"
  
  # Allow overwriting a deleted secret immediately
  recovery_window_in_days = 0 
}

resource "aws_secretsmanager_secret_version" "keys" {
  secret_id     = aws_secretsmanager_secret.keys.id
  
  secret_string = jsonencode({
    OPENROUTER_API_KEY = var.openrouter_api_key
    TAVILY_API_KEY     = var.tavily_api_key
  })
}
