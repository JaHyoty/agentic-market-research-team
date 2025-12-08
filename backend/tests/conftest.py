import pytest
import os
import boto3
import requests
import time
from botocore.exceptions import ClientError

# Set environment keys for testing if not already set (though local-dev sets them)
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")

LOCALSTACK_ENDPOINT = "http://localhost:4566"
API_GATEWAY_URL = "http://localhost:8080"
SQS_QUEUE_NAME = "market-research-tasks"

@pytest.fixture(scope="session")
def sqs_client():
    client = boto3.client(
        "sqs",
        endpoint_url=LOCALSTACK_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return client

@pytest.fixture(scope="session")
def queue_url(sqs_client):
    # Ensure queue exists (it should be created by init scripts, but good to be safe/verified)
    try:
        response = sqs_client.get_queue_url(QueueName=SQS_QUEUE_NAME)
        return response["QueueUrl"]
    except ClientError:
        # Create if not exists (fallback)
        response = sqs_client.create_queue(QueueName=SQS_QUEUE_NAME)
        return response["QueueUrl"]

@pytest.fixture(scope="function")
def clean_queue(sqs_client, queue_url):
    """Purges the queue before each test to ensure a clean state."""
    try:
        sqs_client.purge_queue(QueueUrl=queue_url)
        # SQS purge can take up to 60 seconds to be consistent, but usually fast in LocalStack
        # Just in case, we might want a small sleep if flaky, but let's try without first.
    except Exception as e:
        print(f"Warning: Failed to purge queue: {e}")
    return queue_url

@pytest.fixture
def api_url():
    return API_GATEWAY_URL
