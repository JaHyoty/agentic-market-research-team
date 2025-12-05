import boto3
import sys
import urllib.request
import json
import os

def verify_localstack():
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
    try:
        s3 = boto3.client('s3', endpoint_url=endpoint_url, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
        buckets = s3.list_buckets()
        print("S3 Buckets:", [b['Name'] for b in buckets['Buckets']])
        
        sqs = boto3.client('sqs', endpoint_url=endpoint_url, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
        queues = sqs.list_queues()
        print("SQS Queues:", queues.get('QueueUrls', []))
        
        return True
    except Exception as e:
        print(f"LocalStack verification failed: {e}")
        return False

def verify_dynamodb():
    # Default to localhost:8000 if not set, but if running in docker, we might set DYNAMODB_ENDPOINT
    endpoint_url = os.environ.get('DYNAMODB_ENDPOINT', 'http://localhost:8000')
    try:
        dynamodb = boto3.client('dynamodb', endpoint_url=endpoint_url, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
        tables = dynamodb.list_tables()
        print("DynamoDB Tables:", tables['TableNames'])
        return True
    except Exception as e:
        print(f"DynamoDB verification failed: {e}")
        return False

def verify_api_gateway():
    api_url = os.environ.get('API_GATEWAY_URL', 'http://localhost:8080')
    try:
        with urllib.request.urlopen(f'{api_url}/health') as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get('status') == 'healthy':
                    print("Local API Gateway: Healthy")
                    return True
        print("Local API Gateway: Unhealthy status code")
        return False
    except Exception as e:
        print(f"Local API Gateway verification failed: {e}")
        return False

if __name__ == "__main__":
    ls = verify_localstack()
    ddb = verify_dynamodb()
    api = verify_api_gateway()
    if ls and ddb and api:
        print("Environment Verified!")
    else:
        sys.exit(1)
