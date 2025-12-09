import os
from dotenv import load_dotenv

load_dotenv()

import boto3
import json
import sys

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
    
    # Environment
    ENV = os.getenv("ENV", "local")

    def __init__(self):
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
        self.TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
        
        # If keys are missing, try to fetch from Secrets Manager
        if not self.OPENAI_API_KEY or not self.OPENROUTER_API_KEY or not self.TAVILY_API_KEY:
            self._fetch_secrets()

    def _fetch_secrets(self):
        try:
            print("Fetching secrets from AWS Secrets Manager...")
            if self.ENV == "local":
                client = boto3.client(
                    "secretsmanager",
                    endpoint_url=self.LOCALSTACK_ENDPOINT,
                    region_name=self.AWS_REGION,
                    aws_access_key_id=self.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY
                )
            else:
                client = boto3.client("secretsmanager", region_name=self.AWS_REGION)
            
            response = client.get_secret_value(SecretId="market-research-keys")
            secrets = json.loads(response['SecretString'])
            
            print(f"Secrets response keys: {secrets.keys()}", file=sys.stderr)
            
            if not self.OPENAI_API_KEY:
                self.OPENAI_API_KEY = secrets.get("OPENAI_API_KEY")
                print(f"Set OPENAI_API_KEY from secrets: {bool(self.OPENAI_API_KEY)}", file=sys.stderr)
                if self.OPENAI_API_KEY:
                    os.environ["OPENAI_API_KEY"] = self.OPENAI_API_KEY

            if not self.OPENROUTER_API_KEY:
                self.OPENROUTER_API_KEY = secrets.get("OPENROUTER_API_KEY")
                print(f"Set OPENROUTER_API_KEY from secrets: {bool(self.OPENROUTER_API_KEY)}", file=sys.stderr)
                if self.OPENROUTER_API_KEY:
                    os.environ["OPENROUTER_API_KEY"] = self.OPENROUTER_API_KEY

            if not self.TAVILY_API_KEY:
                self.TAVILY_API_KEY = secrets.get("TAVILY_API_KEY")
                print(f"Set TAVILY_API_KEY from secrets: {bool(self.TAVILY_API_KEY)}", file=sys.stderr)
                if self.TAVILY_API_KEY:
                    os.environ["TAVILY_API_KEY"] = self.TAVILY_API_KEY
                
            print("Secrets fetched successfully.", file=sys.stderr)
        except Exception as e:
            print(f"Failed to fetch secrets: {e}", file=sys.stderr)
            raise e

settings = Config()
