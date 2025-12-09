import time
import json
import traceback
from backend.app.config import settings
from backend.app.utils import get_boto3_client, update_task_status, generate_pdf, upload_to_s3
from backend.app.graph.graph import create_graph
from langchain_core.messages import HumanMessage

def process_message(message):
    try:
        body = json.loads(message['Body'])
        task_id = body.get('task_id')
        query = body.get('query')
        
        if not task_id or not query:
            print("Invalid message format")
            return
            
        print(f"Processing task {task_id}: {query}")
        update_task_status(task_id, "PROCESSING", progress=[f"Started processing: {query}"])
        
        # Initialize graph
        app = create_graph()
        
        # Run graph
        initial_state = {
            "task": query,
            "messages": [HumanMessage(content=query)],
            "revision_count": 0
        }
        
        final_state = app.invoke(initial_state)
        
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
                WaitTimeSeconds=20
            )
            
            messages = response.get('Messages', [])
            for message in messages:
                process_message(message)
                
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
