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
import markdown
import concurrent.futures
from xhtml2pdf import pisa

def process_graph_step(task_id, step_state, tracking_state):
    """Process a single step from the graph stream and update task status."""
    messages = step_state.get('messages', [])
    if not messages:
        return

    last_message = messages[-1]
    msg_type = type(last_message).__name__
    agent_name = getattr(last_message, 'name', None) or "system"
    content_text = parse_response_content(last_message.content)
    content_preview = content_text[:100] + "..." if len(content_text) > 100 else content_text

    print(f"--- State Updated. {msg_type} ({agent_name}): {content_preview[:70]}", file=sys.stderr)

    # 1. Determine Current Agent from Next Step
    next_step = step_state.get('next_step')
    state_current_agent = None
    
    known_agents = ["supervisor", "researcher", "quant", "scout", "writer", "reviewer"]

    if next_step and next_step in known_agents:
        state_current_agent = next_step
    elif next_step == "FINISH":
         # If finish, we might want to show reviewer or supervisor, but let's stick to last active
         pass
    
    # logic for initial state or Supervisor transition (where next_step might be None)
    
    # 2. Update Fallback Tracking
    if agent_name in known_agents:
        tracking_state['previous_agent'] = agent_name

    # 3. Determine Effective Agent for UI
    # Priority: state_current_agent (next_step) > previous_agent (inferred from message)
    # If starting, we might default to Supervisor if nothing else
    effective_agent = state_current_agent or tracking_state['previous_agent'] or "supervisor"

    # 4. Create and Emit Event based on Message Type
    event = None
    
    if msg_type == "ToolMessage":
        # Tool result
        tool_name = agent_name 
        event = create_agent_event(
            agent=tool_name,
            action="tool_result",
            message=f"Tool '{tool_name}' returned result",
            details={"preview": content_preview}
        )
        # Use effective_agent to keep the real agent active in UI
        update_task_status(task_id, "PROCESSING", events=[event], current_agent=effective_agent)
        return

    elif msg_type == "AIMessage" and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        # Agent calling tools
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get('name', 'unknown')
            
            # Skip noise (e.g. scrape_website)
            if tool_name == 'scrape_website':
                continue
            
            tool_args = tool_call.get('args', {})
            
            # Format message based on tool type
            if tool_name == "get_financial_metrics":
                ticker = tool_args.get('ticker', 'unknown')
                tool_msg = f"Fetching financials for {ticker}"
            elif tool_name == "get_stock_price":
                ticker = tool_args.get('ticker', 'unknown')
                tool_msg = f"Fetching stock price for {ticker}"
            else:
                tool_msg = json.dumps(tool_args) if tool_args else f"Calling tool '{tool_name}'"
            
            tool_event = create_agent_event(
                agent=agent_name,
                action="tool_call",
                message=tool_msg,
                details={"tool": tool_name}
            )
            # Use effective_agent or the current agent_name
            update_task_status(task_id, "PROCESSING", events=[tool_event], current_agent=effective_agent or agent_name)
        return

    elif msg_type == "AIMessage":
        # Agent result/output
        event = create_agent_event(
            agent=agent_name,
            action="result",
            message=content_preview
        )
    else:
        # Human/System message
        event = create_agent_event(
            agent="user",
            action="input",
            message=content_preview
        )

    # 5. Emit the main event
    # Use agent_name if known, else usage effective_agent
    current = agent_name if agent_name in known_agents else effective_agent
    update_task_status(task_id, "PROCESSING", events=[event], current_agent=current)

    # 6. Emit "Thinking" Event (Agent Change) - AFTER processing the message
    # Emit "thinking" event if the active agent tracked in state has changed
    if (state_current_agent and 
        state_current_agent != tracking_state['previous_state_agent'] and 
        state_current_agent in known_agents):
        
        thinking_event = create_agent_event(
            agent=state_current_agent,
            action="thinking",
            message=f"{state_current_agent.capitalize()} is analyzing..."
        )
        update_task_status(task_id, "PROCESSING", events=[thinking_event], current_agent=state_current_agent)
        tracking_state['previous_state_agent'] = state_current_agent


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
                "date": datetime.now().strftime("%Y-%m-%d"),
                "current_agent": "supervisor"
            }
        
        # Run graph with streaming for visibility
        final_state = initial_state
        print("Starting graph execution...", file=sys.stderr)
        
        # State tracking for UI updates
        tracking_state = {
            "previous_state_agent": None,
            "previous_agent": None
        }
        
        for step_state in app.stream(initial_state, stream_mode="values", config={"recursion_limit": 100}):
            final_state = step_state
            
            # Process step and emit events
            process_graph_step(task_id, step_state, tracking_state)
                
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
        
        # Generate Report Buffer (PDF)
        print(f"--- Preparing PDF report for task {task_id} ---", file=sys.stderr)
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(report, extensions=['tables'])
        
        # Create PDF
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
             print(f"--- PDF generation error: {pisa_status.err} ---", file=sys.stderr)
             # Fallback to text/markdown if PDF fails
             report_buffer = io.BytesIO(report.encode('utf-8'))
             key = f"{task_id}/report.md"
             s3_url = upload_to_s3(report_buffer, settings.S3_BUCKET_REPORTS, key)
        else:
            print(f"--- PDF generated. Size: {pdf_buffer.getbuffer().nbytes} bytes ---", file=sys.stderr)
            
            # Upload to S3
            print(f"--- Uploading Report to S3 for task {task_id}. Bucket: {settings.S3_BUCKET_REPORTS} ---", file=sys.stderr)
            key = f"{task_id}/report.pdf"
            s3_url = upload_to_s3(pdf_buffer, settings.S3_BUCKET_REPORTS, key)
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
            message="Research report generated successfully (PDF)",
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

def process_with_semaphore(message, sqs, queue_url, semaphore):
    try:
        process_message(message, sqs, queue_url)
    finally:
        semaphore.release()
        
        # Delete message after processing (moved from main loop to ensure it happens after processing)
        # Note: process_message handles visibility extension.
        # Ideally, deletion happens here if successful, but the original code deleted it 
        # immediately after *calling* process_message (synchronously).
        # Since we are now async, we must delete it here or inside process_message.
        # The original code had:
        # process_message(...)
        # sqs.delete_message(...)
        # So it deleted it after processing returned.
        
        try:
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
        except Exception as e:
            print(f"Error deleting message: {e}", file=sys.stderr)


def run_worker():
    sqs = get_boto3_client("sqs")
    queue_url = settings.SQS_QUEUE_URL
    
    print(f"Worker listening on {queue_url}...")
    
    # Thread pool for parallel task execution
    max_workers = 10
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    
    # Semaphore to control polling based on active tasks
    # We acquire before polling/submitting, and release when a task finishes.
    semaphore = threading.Semaphore(max_workers)
    
    error_count = 0
    
    while True:
        try:
            # Block if we have max_workers active tasks
            semaphore.acquire()
            
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20 # Long polling
            )
            
            messages = response.get('Messages', [])
            
            if messages:
                for message in messages:
                    # Submit task to executor
                    # process_with_semaphore will release the semaphore when done
                    executor.submit(process_with_semaphore, message, sqs, queue_url, semaphore)
            else:
                 # No message, release semaphore immediately
                 semaphore.release()
                
        except Exception as e:
            print(f"Error in worker loop: {e}")
            # Ensure we don't leak semaphore permits on error (though acquire is before try, likely)
            # If we acquired but didn't submit, we must release.
            # But the logic above: acquire -> receive -> if messages submit (release in future) -> else release.
            # If receive raises, we must release.
            try:
                semaphore.release()
            except ValueError:
                pass # Might be already released if we are careful, but here just safe-guard
                
            error_count += 1
            if error_count >= 5:
                print("Worker loop error count exceeded. Exiting.")
                break
            time.sleep(5)

if __name__ == "__main__":
    run_worker()
