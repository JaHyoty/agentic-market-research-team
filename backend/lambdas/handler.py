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
s3_client = boto3.client('s3', endpoint_url=endpoint_url, region_name='us-east-1')

sqs = boto3.client('sqs', endpoint_url=endpoint_url, region_name='us-east-1')
dynamodb = boto3.client('dynamodb', endpoint_url=dynamodb_endpoint_url, region_name='us-east-1')

SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL')
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE_TASKS')
S3_BUCKET_REPORTS = os.environ.get('S3_BUCKET_REPORTS', 'market-research-reports')


def submit_handler(event, context):
    print(f"Received submit event: {json.dumps(event)}")
    
    try:
        # Parse body
        body = json.loads(event.get('body', '{}'))
        query = body.get('query')
        
        # Extract browser session ID from headers
        headers = event.get('headers', {})
        browser_session_id = headers.get('x-browser-session-id') or headers.get('X-Browser-Session-Id', '')
        
        if query:
            # NEW TASK START
            max_retries = 3 # Allow for 3 tries to generate a unique task_id
            for attempt in range(max_retries):
                try:
                    task_id = str(uuid.uuid4())
                    timestamp = datetime.utcnow().isoformat()
                    
                    # 2. Write to DynamoDB
                    item = {
                        "task_id": {"S": task_id},
                        "status": {"S": "QUEUED"},
                        "events": {"L": []},
                        "query": {"S": query},
                        "created_at": {"S": timestamp}
                    }
                    # Store browser session ID if provided
                    if browser_session_id:
                        item["browser_session_id"] = {"S": browser_session_id}
                    
                    dynamodb.put_item(
                        TableName=DYNAMODB_TABLE,
                        Item=item,
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
            
            # 3. Trigger Scale-Out if needed (Cold Start Optimization)
            if os.environ.get('ENV') != 'local':
                ecs_cluster = os.environ.get('ECS_CLUSTER_NAME')
                ecs_service = os.environ.get('ECS_SERVICE_NAME')
                
                if ecs_cluster and ecs_service:
                    try:
                        ecs = boto3.client('ecs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
                        resp = ecs.describe_services(cluster=ecs_cluster, services=[ecs_service])
                        services = resp.get('services', [])
                        if services:
                            current_desired = services[0].get('desiredCount', 0)
                            if current_desired == 0:
                                print(f"Triggering scale-out for service {ecs_service}...")
                                ecs.update_service(
                                    cluster=ecs_cluster,
                                    service=ecs_service,
                                    desiredCount=1
                                )
                    except Exception as e:
                        print(f"Error triggering scale-out: {e}")
                        # Non-blocking error, proceed

            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'task_id': task_id,
                    'status': 'QUEUED',
                    'message': 'Research task submitted successfully'
                })
            }
            
        elif body.get('task_id') and body.get('answer'):
            # RESUME TASK
            task_id = body.get('task_id')
            answer = body.get('answer')
            
            # Check current status
            try:
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
                
                current_status = item.get('status', {}).get('S')
                if current_status != 'CLARIFICATION_REQUIRED':
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': f'Task is in {current_status} state, cannot answer clarification.'})
                    }
                    
                # Update DynamoDB with answer and set back to QUEUED
                dynamodb.update_item(
                    TableName=DYNAMODB_TABLE,
                    Key={'task_id': {'S': task_id}},
                    UpdateExpression="SET #s = :s, #a = :a",
                    ExpressionAttributeNames={'#s': 'status', '#a': 'clarification_answer'},
                    ExpressionAttributeValues={
                        ':s': {'S': 'QUEUED'},
                        ':a': {'S': answer}
                    }
                )
                
                # Push Resume Message to SQS
                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MessageBody=json.dumps({
                        "task_id": task_id,
                        "info": "RESUME_WORKFLOW"
                    })
                )
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps({
                        'task_id': task_id,
                        'status': 'QUEUED',
                        'message': 'Clarification answer submitted. Research resuming.'
                    })
                }
                
            except Exception as e:
                print(f"Error resuming task: {e}")
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': f'Error resuming task: {str(e)}'})
                }
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing query OR (task_id and answer)'})
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
        query = item.get('query', {}).get('S')
        created_at = item.get('created_at', {}).get('S')
        
        # Structured events (list of JSON strings)
        events_items = item.get('events', {}).get('L', [])
        events = []
        for e in events_items:
            event_str = e.get('S')
            if event_str:
                try:
                    events.append(json.loads(event_str))
                except json.JSONDecodeError:
                    pass  # Skip malformed events
        
        # Get current active agent
        current_agent = item.get('current_agent', {}).get('S')

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'task_id': task_id,
                'status': status,
                'events': events,
                'report_url': report_url,
                'query': query,
                'created_at': created_at,
                'current_agent': current_agent
            })
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal Server Error'})
        }

def get_sessions_handler(event, context):
    """List research sessions for this browser's session."""
    print(f"Received list_sessions event: {json.dumps(event)}")
    
    try:
        # Extract browser session ID from headers
        headers = event.get('headers', {})
        browser_session_id = headers.get('x-browser-session-id') or headers.get('X-Browser-Session-Id', '')
        
        if not browser_session_id:
            # No session ID, return empty list
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'sessions': []})
            }
        
        # Query for tasks belonging to this browser session
        # Note: 'query' and 'status' are reserved keywords in DynamoDB
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            ProjectionExpression="task_id, #s, created_at, #q, browser_session_id",
            FilterExpression="browser_session_id = :bsid",
            ExpressionAttributeNames={"#s": "status", "#q": "query"},
            ExpressionAttributeValues={":bsid": {"S": browser_session_id}}
        )
        
        sessions = []
        for item in response.get('Items', []):
            sessions.append({
                'task_id': item.get('task_id', {}).get('S'),
                'status': item.get('status', {}).get('S'),
                'created_at': item.get('created_at', {}).get('S'),
                'query': item.get('query', {}).get('S')
            })
        
        # Sort by created_at descending (handle None values)
        sessions.sort(key=lambda x: x.get('created_at') or '', reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'sessions': sessions})
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal Server Error'})
        }

def get_report_handler(event, context):
    print(f"Received get_report event: {json.dumps(event)}")
    
    try:
        task_id = event.get('pathParameters', {}).get('task_id')
        if not task_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing task_id parameter'})
            }
        
        try:
            # Try to get PDF first
            pdf_key = f"{task_id}/report.pdf"
            md_key = f"{task_id}/report.md"
            print(f"DEBUG: Checking bucket '{S3_BUCKET_REPORTS}' for keys: {pdf_key}, {md_key}")

            target_key = None
            filename_ext = ""

            try:
                s3_client.head_object(Bucket=S3_BUCKET_REPORTS, Key=pdf_key)
                print(f"DEBUG: Found PDF: {pdf_key}")
                target_key = pdf_key
                filename_ext = "pdf"
            except ClientError as e:
                print(f"DEBUG: PDF check failed: {e}")
                # Fallback to MD
                try:
                    s3_client.head_object(Bucket=S3_BUCKET_REPORTS, Key=md_key)
                    print(f"DEBUG: Found MD: {md_key}")
                    target_key = md_key
                    filename_ext = "md"
                except ClientError as e2:
                    print(f"DEBUG: MD check failed: {e2}")
                    # Neither found
                    pass
            
            if not target_key:
                 print(f"DEBUG: Report not found for task {task_id}")
                 return {
                    'statusCode': 404,
                    'body': json.dumps({'error': f'Report not found in bucket {S3_BUCKET_REPORTS}. Checked {pdf_key} and {md_key}'})
                }

            # Generate presigned URL
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_BUCKET_REPORTS,
                    'Key': target_key,
                    'ResponseContentDisposition': f'inline; filename="report-{task_id}.{filename_ext}"',
                    'ResponseContentType': 'application/pdf' if filename_ext == 'pdf' else 'text/markdown'
                },
                ExpiresIn=3600
            )
            
            # Fix LocalStack URL for browser access
            if 'localstack:4566' in url:
                url = url.replace('localstack:4566', 'localhost:4566')
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'url': url})
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"ClientError: {error_code}, {e}")
            raise e

    except Exception as e:
        print(f"Error fetching report: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Internal Server Error: {str(e)}'})
        }
