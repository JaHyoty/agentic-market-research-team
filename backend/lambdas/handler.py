import json
import boto3
import os
import uuid
import time
from datetime import datetime
from botocore.exceptions import ClientError

# Initialize clients outside handler for reuse
endpoint_url = os.environ.get('AWS_ENDPOINT_URL') # For LocalStack
dynamodb_endpoint_url = os.environ.get('DYNAMODB_ENDPOINT', endpoint_url) # Specific for DynamoDB Local

sqs = boto3.client('sqs', endpoint_url=endpoint_url, region_name='us-east-1')
dynamodb = boto3.client('dynamodb', endpoint_url=dynamodb_endpoint_url, region_name='us-east-1')

SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE_TASKS')

def submit_handler(event, context):
    print(f"Received submit event: {json.dumps(event)}")
    
    try:
        # Parse body
        body = json.loads(event.get('body', '{}'))
        query = body.get('query')
        
        if not query:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing query parameter'})
            }
            

        max_retries = 3
        for attempt in range(max_retries):
            try:
                task_id = str(uuid.uuid4())
                timestamp = datetime.utcnow().isoformat()
                
                # 2. Write to DynamoDB
                dynamodb.put_item(
                    TableName=DYNAMODB_TABLE,
                    Item={
                        "task_id": {"S": task_id},
                        "status": {"S": "QUEUED"},
                        "progress": {"L": []},
                        "created_at": {"S": timestamp}
                    },
                    ConditionExpression='attribute_not_exists(task_id)'
                )
                break # Success
            except ClientError as e:
                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    if attempt == max_retries - 1:
                        raise Exception("Failed to generate unique task_id after multiple attempts")
                    continue # Try again with new ID
                raise e

        # 1. Push to SQS (moved after DB write to ensure DB record exists first)
        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps({
                "task_id": task_id,
                "query": query
            })
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'task_id': task_id,
                'status': 'QUEUED',
                'message': 'Research task submitted successfully'
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal Server Error'})
        }

def get_status_handler(event, context):
    print(f"Received get_status event: {json.dumps(event)}")
    
    try:
        task_id = event.get('pathParameters', {}).get('task_id')
        if not task_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing task_id parameter'})
            }

        response = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={'task_id': {'S': task_id}}
        )
        
        item = response.get('Item')
        if not item:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Task not found'})
            }

        # Format response to match Pydantic model
        # DynamoDB returns types like {'S': 'val'}, we need to unmarshal or manually extract
        status = item.get('status', {}).get('S', 'UNKNOWN')
        report_url = item.get('report_url', {}).get('S')
        
        # Progress logs are a list of strings
        progress_items = item.get('progress', {}).get('L', [])
        progress_logs = [p.get('S') for p in progress_items if p.get('S')]

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'task_id': task_id,
                'status': status,
                'progress': progress_logs,
                'report_url': report_url
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal Server Error'})
        }
