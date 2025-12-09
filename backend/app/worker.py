import time
import json
import traceback
import sys
from backend.app.config import settings
from backend.app.utils import get_boto3_client, update_task_status, generate_pdf, upload_to_s3
from backend.app.graph.graph import create_graph
from langchain_core.messages import HumanMessage

import threading

def process_message(message, sqs_client, queue_url):
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = None

    try:
        body = json.loads(message['Body'])
        task_id = body.get('task_id')
        query = body.get('query')
        receipt_handle = message['ReceiptHandle']
        
        if not task_id or not query:
            print("Invalid message format")
            return
            
        print(f"Processing task {task_id}: {query}")
        update_task_status(task_id, "PROCESSING", progress=[f"Started processing: {query}"])
        
        # Start Heartbeat
        def heartbeat():
            while not heartbeat_stop_event.is_set():
                try:
                    sqs_client.change_message_visibility(
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle,
                        VisibilityTimeout=60 
                    )
                    # print(f"Heartbeat: Extended visibility for task {task_id}", file=sys.stderr)
                    time.sleep(30) # Wait 30s before extending again (buffer for 60s timeout)
                except Exception as e:
                    print(f"Heartbeat failed: {e}", file=sys.stderr)
                    # If heartbeat fails (e.g. message deleted), stopping might be good, but for now just retry/log
                    time.sleep(30)

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        # Initialize graph
        app = create_graph()
        
        # Run graph
        initial_state = {
            "task": query,
            "messages": [HumanMessage(content=query)],
            "revision_count": 0
        }
        
        # Run graph with streaming for visibility
        final_state = initial_state
        print("Starting graph execution...", file=sys.stderr)
        for step_state in app.stream(initial_state, stream_mode="values"):
            final_state = step_state
            # Log progress based on state changes
            last_message = final_state['messages'][-1] if final_state.get('messages') else None
            if last_message:
                content_preview = str(last_message.content)[:70] + "..." if len(str(last_message.content)) > 70 else str(last_message.content)
                print(f"--- State Updated. Last Message: {type(last_message).__name__}: {content_preview} ---", file=sys.stderr)
        print("Graph execution completed.", file=sys.stderr)
        
        # Extract report
        report = final_state.get('draft_report', 'No report generated.')
        
        # Generate PDF
        pdf_buffer = generate_pdf(report)
        
        # Upload to S3
        key = f"{task_id}/report.pdf"
        s3_url = upload_to_s3(pdf_buffer, settings.S3_BUCKET_REPORTS, key)
        
        # Update status
        update_task_status(task_id, "COMPLETED", progress=["Report generated"], report_url=s3_url)
        print(f"Task {task_id} completed.")
        
    except Exception as e:
        print(f"Error processing message: {e}")
        traceback.print_exc()
        if task_id:
            update_task_status(task_id, "FAILED", progress=[f"Error: {str(e)}"])
    finally:
        # Stop Heartbeat
        if heartbeat_thread:
            heartbeat_stop_event.set()
            heartbeat_thread.join(timeout=2)

def run_worker():
    sqs = get_boto3_client("sqs")
    queue_url = settings.SQS_QUEUE_URL
    
    print(f"Worker listening on {queue_url}...")
    error_count = 0
    
    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20 # Long polling
            )
            
            messages = response.get('Messages', [])
            for message in messages:
                # Pass client and queue_url for heartbeat
                process_message(message, sqs, queue_url)
                
                # Delete message
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                
        except Exception as e:
            print(f"Error in worker loop: {e}")
            error_count += 1
            if error_count >= 5:
                print("Worker loop error count exceeded. Exiting.")
                break
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
