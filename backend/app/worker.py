import time
import json
import traceback
import sys
import io
from datetime import datetime
from backend.app.config import settings
from backend.app.utils import get_boto3_client, update_task_status, upload_to_s3, parse_response_content, deserialize_state, serialize_state, create_agent_event
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
        
        if not task_id:
            raise ValueError("Invalid message format: missing task_id")
            
        # Check for saved state (resume)
        dynamodb = get_boto3_client("dynamodb")
        item = dynamodb.get_item(
            TableName=settings.DYNAMODB_TABLE_TASKS,
            Key={"task_id": {"S": task_id}},
            ConsistentRead=True
        ).get('Item', {})
        
        saved_state_str = item.get('state', {}).get('S')
        clarification_answer = item.get('clarification_answer', {}).get('S')
        
        print(f"DEBUG: Task {task_id} state loaded. State len: {len(saved_state_str) if saved_state_str else 0}, Answer: {clarification_answer}", file=sys.stderr)
        
        initial_state = None
        if saved_state_str and clarification_answer:
            print(f"Resuming task {task_id} with answer.", file=sys.stderr)
            update_task_status(task_id, "PROCESSING", events=[create_agent_event(
                agent="system",
                action="info",
                message=f"Resuming with answer: {clarification_answer}"
            )])
            
            # Deserialize
            initial_state = deserialize_state(saved_state_str)
            
            # Reset state for resumption
            initial_state['next_step'] = None
            initial_state['clarification_question'] = None
            
            # Update task definition with clarification
            initial_state['task'] += f"\n\nClarification: {clarification_answer}"
            
            # Inject answer as user message
            initial_state['messages'].append(HumanMessage(content=clarification_answer))
            
            # Clean up answer from DB (optional, but cleaner)
            dynamodb.update_item(
            TableName=settings.DYNAMODB_TABLE_TASKS,
            Key={"task_id": {"S": task_id}},
            UpdateExpression="REMOVE clarification_answer"
            )
        else:
            if not query:
                raise ValueError("Invalid message format: missing query")

            print(f"Processing task {task_id}: {query}")
            update_task_status(task_id, "PROCESSING", events=[create_agent_event(
                agent="system",
                action="info",
                message=f"Started processing: {query}"
            )])
        
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
        if not initial_state:
            initial_state = {
                "task": query,
                "messages": [HumanMessage(content=query)],
                "revision_count": 0,
                "date": datetime.now().strftime("%Y-%m-%d")
            }
        
        # Run graph with streaming for visibility
        final_state = initial_state
        last_event_count = 0  # Track events to avoid duplicate updates
        print("Starting graph execution...", file=sys.stderr)
        
        for step_state in app.stream(initial_state, stream_mode="values", config={"recursion_limit": 100}):
            final_state = step_state
            
            # Get the last message for event creation
            messages = final_state.get('messages', [])
            if not messages:
                continue
                
            last_message = messages[-1]
            msg_type = type(last_message).__name__
            agent_name = getattr(last_message, 'name', None) or "system"
            content_text = parse_response_content(last_message.content)
            content_preview = content_text[:100] + "..." if len(content_text) > 100 else content_text
            
            print(f"--- State Updated. {msg_type} ({agent_name}): {content_preview[:70]}", file=sys.stderr)
            
            # Determine action type based on message type
            if msg_type == "ToolMessage":
                # Tool result
                tool_name = agent_name  # ToolMessage.name is the tool name
                event = create_agent_event(
                    agent=tool_name,
                    action="tool_result",
                    message=f"Tool '{tool_name}' returned result",
                    details={"preview": content_preview}
                )
            elif msg_type == "AIMessage" and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                # Agent making a tool call
                for tool_call in last_message.tool_calls:
                    tool_name = tool_call.get('name', 'unknown')
                    tool_args = tool_call.get('args', {})
                    tool_msg = json.dumps(tool_args) if tool_args else f"Calling tool '{tool_name}'"
                    event = create_agent_event(
                        agent=agent_name,
                        action="tool_call",
                        message=tool_msg,
                        details={"tool": tool_name}
                    )
                    update_task_status(task_id, "PROCESSING", events=[event])
                continue  # Skip the regular event update for tool calls
            elif msg_type == "AIMessage":
                # Agent produced a result/thinking
                event = create_agent_event(
                    agent=agent_name,
                    action="result",
                    message=content_preview
                )
            else:
                # Human message or other
                event = create_agent_event(
                    agent="user",
                    action="input",
                    message=content_preview
                )
            
            # Emit structured event to DynamoDB
            update_task_status(task_id, "PROCESSING", events=[event])
                
            # Check for clarification request
            if final_state.get('next_step') == 'ask_question':
                question = final_state.get('clarification_question', 'Clarification needed.')
                print(f"--- Pausing for clarification: {question}", file=sys.stderr)
                
                # Serialize state
                serialized_state = serialize_state(final_state)
                
                # Emit clarification event
                clarification_event = create_agent_event(
                    agent="supervisor",
                    action="clarification",
                    message=question
                )
                
                # Update status and save state
                update_task_status(
                    task_id, 
                    "CLARIFICATION_REQUIRED", 
                    events=[clarification_event],
                    state=serialized_state
                )
                print(f"Task {task_id} paused for clarification.")
                return # Exit processing, do not generate report

        print("Graph execution completed.", file=sys.stderr)
        
        # Extract report
        print(f"--- Extracting report for task {task_id} ---", file=sys.stderr)
        report = final_state.get('draft_report', 'No report generated.')
        print(f"--- Report extracted. Length: {len(report)} characters ---", file=sys.stderr)
        
        # Generate Report Buffer (Markdown)
        print(f"--- Preparing Markdown report for task {task_id} ---", file=sys.stderr)
        # Convert string to bytes for S3 upload
        report_buffer = io.BytesIO(report.encode('utf-8'))
        print(f"--- Report buffer ready. Size: {report_buffer.getbuffer().nbytes} bytes ---", file=sys.stderr)
        
        # Upload to S3
        print(f"--- Uploading Report to S3 for task {task_id}. Bucket: {settings.S3_BUCKET_REPORTS} ---", file=sys.stderr)
        key = f"{task_id}/report.md"
        s3_url = upload_to_s3(report_buffer, settings.S3_BUCKET_REPORTS, key)
        print(f"--- Report uploaded to S3. URL: {s3_url} ---", file=sys.stderr)
        
        # Save Full Log to Markdown
        print(f"--- Saving Full Log for task {task_id} ---", file=sys.stderr)
        log_content = f"# Conversation Log for Task {task_id}\n\n"
        log_content += f"**Query:** {query}\n"
        log_content += f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        log_content += "---\n\n"
        
        if final_state.get('messages'):
            for msg in final_state['messages']:
                role = type(msg).__name__
                sender = msg.name if hasattr(msg, 'name') and msg.name else role
                content = parse_response_content(msg.content)
                log_content += f"### {role} ({sender})\n\n"
                log_content += f"{content}\n\n"
                log_content += "---\n\n"
                
        log_buffer = io.BytesIO(log_content.encode('utf-8'))
        log_key = f"{task_id}/logs.md"
        log_url = upload_to_s3(log_buffer, settings.S3_BUCKET_REPORTS, log_key)
        print(f"--- Logs uploaded to S3. URL: {log_url} ---", file=sys.stderr)
        
        # Update status with completion event
        print(f"--- Updating task status to COMPLETED for task {task_id} ---", file=sys.stderr)
        completion_event = create_agent_event(
            agent="system",
            action="complete",
            message="Research report generated successfully",
            details={"report_url": s3_url}
        )
        update_task_status(task_id, "COMPLETED", events=[completion_event], report_url=s3_url)

        print(f"Task {task_id} completed.")
        
    except Exception as e:
        print(f"Error processing message: {e}")
        traceback.print_exc()
        if task_id:
            error_event = create_agent_event(
                agent="system",
                action="error",
                message=f"Task failed: {str(e)}"
            )
            update_task_status(task_id, "FAILED", events=[error_event])
        print(f"Task {task_id} failed.")

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
