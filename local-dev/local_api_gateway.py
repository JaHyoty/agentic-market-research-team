import uvicorn
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import sys

# Import the actual Lambda handlers
# Add project root to python path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables for LocalStack BEFORE importing handler
# Only set if not already present (to allow docker-compose to override)
if not os.environ.get('AWS_ENDPOINT_URL'):
    os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:4566'
if not os.environ.get('AWS_ACCESS_KEY_ID'):
    os.environ['AWS_ACCESS_KEY_ID'] = 'test'
if not os.environ.get('AWS_SECRET_ACCESS_KEY'):
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'
if not os.environ.get('AWS_REGION'):
    os.environ['AWS_REGION'] = 'us-east-1'
if not os.environ.get('DYNAMODB_ENDPOINT'):
    os.environ['DYNAMODB_ENDPOINT'] = 'http://localhost:8000'
if not os.environ.get('SQS_QUEUE_URL'):
    os.environ['SQS_QUEUE_URL'] = 'http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/market-research-tasks'
if not os.environ.get('DYNAMODB_TABLE_TASKS'):
    os.environ['DYNAMODB_TABLE_TASKS'] = 'market-research-tasks'

# Import the actual Lambda handlers
from backend.lambdas.handler import submit_handler, get_status_handler, list_sessions_handler, get_report_handler

app = FastAPI(title="Local API Gateway Emulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/research")
async def proxy_submit(request: Request):
    body = await request.json()
    
    # Construct Lambda Event with headers
    event = {
        "body": json.dumps(body),
        "headers": dict(request.headers)
    }
    context = {} # Mock context
    
    response = submit_handler(event, context)
    
    if response['statusCode'] >= 400:
        raise HTTPException(status_code=response['statusCode'], detail=json.loads(response['body']))
        
    return json.loads(response['body'])

@app.get("/tasks/{task_id}")
async def proxy_get_status(task_id: str):
    # Construct Lambda Event
    event = {
        "pathParameters": {
            "task_id": task_id
        }
    }
    context = {}
    
    response = get_status_handler(event, context)
    
    if response['statusCode'] >= 400:
        raise HTTPException(status_code=response['statusCode'], detail=json.loads(response['body']))
        
    return json.loads(response['body'])


@app.get("/sessions")
async def proxy_list_sessions(request: Request):
    """List research sessions for this browser."""
    event = {
        "headers": dict(request.headers)
    }
    context = {}
    
    response = list_sessions_handler(event, context)
    
    if response['statusCode'] >= 400:
        raise HTTPException(status_code=response['statusCode'], detail=json.loads(response['body']))
        
    return json.loads(response['body'])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/reports/{task_id}")
async def get_report(task_id: str):
    """Download the report for a task."""
    event = {
        "pathParameters": {
            "task_id": task_id
        }
    }
    context = {}
    
    response = get_report_handler(event, context)
    
    if response['statusCode'] >= 400:
        error_detail = response.get('body', 'Unknown error')
        try:
            error_detail = json.loads(error_detail)
        except:
            pass
        raise HTTPException(status_code=response['statusCode'], detail=error_detail)
        
    return Response(
        content=response['body'],
        headers=response.get('headers', {})
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)