import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    
    # LocalStack endpoints
    LOCALSTACK_ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
    DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    
    # Resource names
    SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/market-research-tasks")
    S3_BUCKET_ARTIFACTS = os.getenv("S3_BUCKET_ARTIFACTS", "market-research-artifacts")
    S3_BUCKET_REPORTS = os.getenv("S3_BUCKET_REPORTS", "market-research-reports")
    DYNAMODB_TABLE_TASKS = os.getenv("DYNAMODB_TABLE_TASKS", "market-research-tasks")
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    
    # Environment
    ENV = os.getenv("ENV", "local")

settings = Config()
