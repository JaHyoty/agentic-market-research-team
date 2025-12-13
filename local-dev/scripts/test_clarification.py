import requests
import time
import json
import sys
import boto3
import os

# Configuration (match local-dev defaults)
API_URL = "http://localhost:8080"

def test_clarification_flow():
    print("--- Starting Clarification Flow Test ---")
    
    # 1. Submit Vague Task
    vague_query = "Do some research"
    print(f"1. Submitting vague query: '{vague_query}'")
    response = requests.post(f"{API_URL}/research", json={"query": vague_query})
    if response.status_code != 200:
        print(f"Failed to submit task: {response.text}")
        sys.exit(1)
        
    task_id = response.json()['task_id']
    print(f"   Task ID: {task_id}")
    
    # 2. Poll for CLARIFICATION_REQUIRED
    print("2. Polling for CLARIFICATION_REQUIRED status...")
    max_retries = 30
    clarification_question = None
    
    for i in range(max_retries):
        status_res = requests.get(f"{API_URL}/tasks/{task_id}")
        if status_res.status_code == 200:
            data = status_res.json()
            status = data['status']
            progress = data.get('progress', [])
            print(f"   Status: {status}")
            
            if status == "CLARIFICATION_REQUIRED":
                # Extract question from progress if possible, or just assume success
                # Our worker implementation logs "Clarification asked: <Question>"
                for log in progress:
                    if "Clarification asked:" in log:
                        clarification_question = log
                print(f"   Clarification Requested: {clarification_question}")
                break
        else:
            print(f"   Failed to get status: {status_res.text}")
            
        time.sleep(2)
    else:
        print("   Timeout waiting for CLARIFICATION_REQUIRED")
        sys.exit(1)
        
    # 3. Submit Answer
    answer = "Create a comprehensive strategy report for Apple Inc. for the year 2025, focusing on their AI initiatives."
    print(f"3. Submitting answer: '{answer}'")
    answer_res = requests.post(f"{API_URL}/research", json={"task_id": task_id, "answer": answer})
    
    if answer_res.status_code != 200:
        print(f"Failed to submit answer: {answer_res.text}")
        sys.exit(1)
        
    print(f"   Answer submitted: {answer_res.json()['message']}")
    
    # 4. Poll for COMPLETION
    print("4. Polling for COMPLETED status...")
    for i in range(120): # Longer wait for research
        status_res = requests.get(f"{API_URL}/tasks/{task_id}")
        data = status_res.json()
        status = data['status']
        print(f"   Status: {status}")
        
        if status == "COMPLETED":
            print(f"   Task Completed! Report URL: {data.get('report_url')}")
            # Trigger sync script
            print("\nSyncing reports to local-dev/reports...")
            try:
                subprocess.run(["./local-dev/scripts/sync_reports.sh"], check=True)
            except Exception as e:
                print(f"Failed to sync reports: {e}")
            break
        if status == "FAILED":
             print("   Task Failed.")
             sys.exit(1)
        if status == "CLARIFICATION_REQUIRED":
             print("   Task Paused for further clarification.")
             sys.exit(1)
             
        time.sleep(2)
    else:
        print("   Timeout waiting for COMPLETED")
        sys.exit(1)

    print("--- Test Passed ---")

if __name__ == "__main__":
    test_clarification_flow()
