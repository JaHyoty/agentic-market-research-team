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
DYNAMODB_ENDPOINT = "http://localhost:8000"
DYNAMODB_TABLE_NAME = "market-research-tasks"

@pytest.fixture(scope="session")
def dynamodb_client():
    client = boto3.client(
        "dynamodb",
        endpoint_url=DYNAMODB_ENDPOINT,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return client

@pytest.fixture(scope="session")
def dynamodb_table(dynamodb_client):
    # Ensure table exists
    try:
        dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
    except ClientError:
        # Create if not exists (backend should handle this usually via init scripts, but for tests we want certainty)
        dynamodb_client.create_table(
            TableName=DYNAMODB_TABLE_NAME,
            KeySchema=[{'AttributeName': 'task_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'task_id', 'AttributeType': 'S'}],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
    return DYNAMODB_TABLE_NAME

@pytest.fixture(scope="function")
def clean_dynamodb(dynamodb_client, dynamodb_table):
    """Cleans up the DynamoDB table after the test."""
    yield
    try:
        # Scan and delete all items
        scan = dynamodb_client.scan(TableName=dynamodb_table)
        items = scan.get("Items", [])
        if items:
            # Let's iterate and delete for simplicity and reliability in tests
            for item in items:
                dynamodb_client.delete_item(
                    TableName=dynamodb_table,
                    Key={'task_id': item['task_id']}
                )
    except Exception as e:
        print(f"Warning: Failed to clean DynamoDB: {e}")

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
    """Purges the queue after the test to ensure a clean state."""
    yield
    try:
        sqs_client.purge_queue(QueueUrl=queue_url)
        # SQS purge can take up to 60 seconds to be consistent, but usually fast in LocalStack
        # Just in case, we might want a small sleep if flaky, but let's try without first.
    except Exception as e:
        print(f"Warning: Failed to purge queue: {e}")

@pytest.fixture
def api_url():
    return API_GATEWAY_URL
