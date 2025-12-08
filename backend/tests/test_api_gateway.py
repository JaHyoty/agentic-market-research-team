import pytest
import requests
import json
import time

def test_health_check(api_url):
    response = requests.get(f"{api_url}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_submit_research_queues_message(api_url, sqs_client, queue_url, clean_queue):
    payload = {
        "query": "Test research query",
        "detailed_report": False
    }
    
    # 1. Submit research request
    response = requests.post(f"{api_url}/research", json=payload)
    assert response.status_code == 200
    response_data = response.json()
    assert "task_id" in response_data
    task_id = response_data["task_id"]
    
    # 2. Verify message in SQS
    # Poll briefly as it might be async (though local api is synchronous in pushing to sqs usually)
    messages = []
    for _ in range(5):
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1
        )
        if "Messages" in response:
            messages = response["Messages"]
            break
        time.sleep(0.5)
        
    assert len(messages) == 1, "Expected 1 message in SQS"
    
    body = json.loads(messages[0]["Body"])
    # The API might wrap the body or send it directly. 
    # Based on local_api_gateway.py: submit_handler -> dumps body. 
    # Let's see what the backend actually sends. 
    # Usually the backend submit_handler (Lambda) sends the event body to SQS or similar.
    # We will verify the content matches our payload.
    
    # Depending on how the lambda handles it, the message body in SQS might be the raw payload 
    # or wrapped. We'll check if our query is present.
    assert "Test research query" in messages[0]["Body"]
    assert task_id in messages[0]["Body"]
