#!/bin/bash
echo "Initializing LocalStack resources..."

# S3 Buckets
awslocal s3 mb s3://market-research-artifacts
awslocal s3 mb s3://market-research-reports

# SQS Queue
awslocal sqs create-queue --queue-name market-research-tasks

# DynamoDB Table
awslocal dynamodb create-table \
    --table-name market-research-tasks \
    --key-schema AttributeName=task_id,KeyType=HASH \
    --attribute-definitions AttributeName=task_id,AttributeType=S \
    --billing-mode PAY_PER_REQUEST || true

# Read API keys from .env file if it exists
ENV_FILE="/etc/localstack/init/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Reading API keys from .env file..."
    source "$ENV_FILE"
else
    echo "Warning: .env file not found at $ENV_FILE, using mock keys"
fi

# Set defaults if not provided
TAVILY_API_KEY="${TAVILY_API_KEY:-mock-tavily-key}"
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-mock-openrouter-key}"
OPENAI_API_KEY="${OPENAI_API_KEY:-mock-openai-key}"

# Secrets Manager
SECRET_STRING=$(cat <<EOF
{"OPENAI_API_KEY":"${OPENAI_API_KEY}","TAVILY_API_KEY":"${TAVILY_API_KEY}","OPENROUTER_API_KEY":"${OPENROUTER_API_KEY}"}
EOF
)

awslocal secretsmanager create-secret \
    --name market-research-keys \
    --secret-string "$SECRET_STRING" || \
awslocal secretsmanager update-secret \
    --secret-id market-research-keys \
    --secret-string "$SECRET_STRING"

echo "LocalStack resources initialized."
