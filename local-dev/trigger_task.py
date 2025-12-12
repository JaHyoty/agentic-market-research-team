import boto3
import json
import uuid
import os
import time
import sys
import subprocess
from kubernetes import client, config

def trigger_and_watch():
    # 1. Setup AWS/LocalStack Client
    endpoint_url = os.environ.get('AWS_ENDPOINT_URL', 'http://localhost:4566')
    queue_url = os.environ.get('SQS_QUEUE_URL', 'http://localhost:4566/000000000000/market-research-tasks')
    
    sqs = boto3.client('sqs', endpoint_url=endpoint_url, aws_access_key_id='test', aws_secret_access_key='test', region_name='us-east-1')
    
    # 2. Send Task
    task_id = str(uuid.uuid4())
    message_body = {
        "task_id": task_id,
        "query": "What is the market size of BEV sales in the US?"
    }
    
    print(f"Sending task {task_id} to {queue_url}...")
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )
    print(f"Message Sent. ID: {response['MessageId']}")
    
    # 3. Setup Kubernetes Client
    # Only load config if not in-cluster (this script is local)
    try:
        config.load_kube_config(config_file="local-dev/kubeconfig/kubeconfig.yaml")
    except Exception as e:
        print(f"Failed to load kubeconfig: {e}")
        print("Ensure 'local-dev/kubeconfig/kubeconfig.yaml' exists.")
        return

    v1 = client.CoreV1Api()
    
    print(f"Waiting for a worker to start processing task {task_id}...")
    
    target_pod = None
    max_retries = 30 # Poll for ~60s
    
    # 4. Find the pod processing this task
    for i in range(max_retries):
        try:
            # Get all worker pods
            pods = v1.list_namespaced_pod(namespace="default", label_selector="app=market-research-worker")
            
            for pod in pods.items:
                if pod.status.phase == "Running":
                    # Check recent logs
                    try:
                        logs = v1.read_namespaced_pod_log(name=pod.metadata.name, namespace="default", tail_lines=20)
                        if f"Processing task {task_id}" in logs:
                            target_pod = pod.metadata.name
                            print(f"\nFound worker: {target_pod}")
                            break
                    except Exception:
                        continue # Pod might be initializing
            
            if target_pod:
                break
            
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(2)
            
        except Exception as e:
            print(f"Error polling k8s: {e}")
            time.sleep(2)
            
    if not target_pod:
        print("\nTimed out waiting for worker to pick up task.")
        return

    # 5. Stream logs using kubectl (easier for robust streaming than python client)
    print(f"Streaming logs from {target_pod}...\n" + "="*50)
    
    try:
        # Use subprocess to tail logs
        process = subprocess.Popen(
            ["kubectl", "--kubeconfig", "local-dev/kubeconfig/kubeconfig.yaml", "logs", "-f", target_pod],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Read stream
        completed = False
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(line, end='')
                if f"Task {task_id} completed" in line or f"Task {task_id} failed" in line:
                    completed = True
                    # We continue briefly to flush any remaining logs then exit?
                    # The worker continues running, so 'process' won't exit.
                    # We intentionally break here.
                    print("\n" + "="*50)
                    print(f"Task finished based on logs.")
                    process.terminate()

                    # Trigger sync script
                    print("\nSyncing reports to local-dev/reports...")
                    try:
                        subprocess.run(["./local-dev/scripts/sync_reports.sh"], check=True)
                    except Exception as e:
                        print(f"Failed to sync reports: {e}")
                    
                    break
                    
    except KeyboardInterrupt:
        print("\nStreaming stopped by user.")
        if process:
            process.terminate()

if __name__ == "__main__":
    trigger_and_watch()
