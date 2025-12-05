import boto3
import sys

def verify_localstack():
    try:
        s3 = boto3.client('s3', endpoint_url='http://localhost:4566', aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
        buckets = s3.list_buckets()
        print("S3 Buckets:", [b['Name'] for b in buckets['Buckets']])
        
        sqs = boto3.client('sqs', endpoint_url='http://localhost:4566', aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
        queues = sqs.list_queues()
        print("SQS Queues:", queues.get('QueueUrls', []))
        
        return True
    except Exception as e:
        print(f"LocalStack verification failed: {e}")
        return False

def verify_dynamodb():
    try:
        dynamodb = boto3.client('dynamodb', endpoint_url='http://localhost:8000', aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
        tables = dynamodb.list_tables()
        print("DynamoDB Tables:", tables['TableNames'])
        return True
    except Exception as e:
        print(f"DynamoDB verification failed: {e}")
        return False

if __name__ == "__main__":
    ls = verify_localstack()
    ddb = verify_dynamodb()
    if ls and ddb:
        print("Environment Verified!")
    else:
        sys.exit(1)
