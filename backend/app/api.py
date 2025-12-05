from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import json
from backend.app.models.schema import ResearchRequest, ResearchResponse, TaskStatus
from backend.app.config import settings
from backend.app.utils import get_boto3_client

app = FastAPI(title="Agentic Market Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/research", response_model=ResearchResponse)
async def submit_research(request: ResearchRequest):
    task_id = str(uuid.uuid4())
    
    # Push to SQS
    sqs = get_boto3_client("sqs")
    sqs.send_message(
        QueueUrl=settings.SQS_QUEUE_URL,
        MessageBody=json.dumps({
            "task_id": task_id,
            "query": request.query
        })
    )
    
    # Initialize status in DynamoDB
    dynamodb = get_boto3_client("dynamodb")
    dynamodb.put_item(
        TableName=settings.DYNAMODB_TABLE_TASKS,
        Item={
            "task_id": {"S": task_id},
            "status": {"S": "QUEUED"},
            "progress": {"L": []},
            "created_at": {"S": str(uuid.uuid1())} # timestamp
        }
    )
    
    return ResearchResponse(
        task_id=task_id,
        status="QUEUED",
        message="Research task submitted successfully"
    )

@app.get("/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    dynamodb = get_boto3_client("dynamodb")
    response = dynamodb.get_item(
        TableName=settings.DYNAMODB_TABLE_TASKS,
        Key={"task_id": {"S": task_id}}
    )
    
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
        
    progress = [p["S"] for p in item.get("progress", {}).get("L", [])]
    report_url = item.get("report_url", {}).get("S")
    
    return TaskStatus(
        task_id=task_id,
        status=item["status"]["S"],
        progress=progress,
        report_url=report_url
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
