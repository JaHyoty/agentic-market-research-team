import boto3
import json
import uuid
import os

def send_task():
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
    queue_url = os.environ.get('SQS_QUEUE_URL', 'http://localhost:4566/000000000000/market-research-tasks')
    
    sqs = boto3.client('sqs', endpoint_url=endpoint_url, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
    
    task_id = str(uuid.uuid4())
    message_body = {
        "task_id": task_id,
        "query": "Test research query for scaling verification"
    }
    
    print(f"Sending task {task_id} to {queue_url}...")
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )
    print(f"Message Sent. ID: {response['MessageId']}")

if __name__ == "__main__":
    send_task()
