import boto3
from backend.app.config import settings
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from langchain_core.messages import messages_to_dict, messages_from_dict
import markdown
import json
import io
from datetime import datetime
from typing import Optional, Dict, Any, List, Union


def create_agent_event(
    agent: str,
    action: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a structured event for real-time agent visualization.
    
    Args:
        agent: Agent name (supervisor, researcher, quant, scout, writer, reviewer, or tool name)
        action: Event type - 'thinking', 'tool_call', 'tool_result', 'result', 'error'
        message: Human-readable description of what's happening
        details: Optional additional data (tool args, results preview, etc.)
    
    Returns:
        Structured event dict ready for DynamoDB storage
    """
    event = {
        "agent": agent,
        "action": action,
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    if details:
        event["details"] = details
    return event

def parse_response_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = ""
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        return text if text else str(content)
    return str(content)

def get_boto3_client(service_name):
    if settings.ENV == "local":
        endpoint_url = settings.DYNAMODB_ENDPOINT if service_name == "dynamodb" else settings.LOCALSTACK_ENDPOINT
        return boto3.client(
            service_name,
            endpoint_url=endpoint_url,
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
    return boto3.client(service_name, region_name=settings.AWS_REGION)

def generate_pdf(markdown_text):
    """Convert markdown text to a simple PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Convert markdown to HTML (simple conversion)
    html = markdown.markdown(markdown_text)
    
    # For reportlab, we need to parse this properly or just treat as text
    # Since reportlab doesn't ingest HTML natively without heavy libs, 
    # we will just add the text as paragraphs for this prototype.
    # A real implementation would use a proper MD->PDF converter.
    
    for line in markdown_text.split('\n'):
        if line.strip():
            # Basic styling based on markdown headers
            style = styles["BodyText"]
            if line.startswith("# "):
                style = styles["Heading1"]
                line = line[2:]
            elif line.startswith("## "):
                style = styles["Heading2"]
                line = line[3:]
            elif line.startswith("### "):
                style = styles["Heading3"]
                line = line[4:]
            
            # Sanitize line for ReportLab XML parser
            # ReportLab requires self-closing tags like <br/> and doesn't like content inside them
            line = line.replace('<br>', '<br/>').replace('</br>', '')
            
            try:
                story.append(Paragraph(line, style))
            except Exception as e:
                # Fallback if parsing keeps failing: escape and print as plain text
                import html as html_lib
                safe_line = html_lib.escape(line)
                story.append(Paragraph(safe_line, style))
            story.append(Spacer(1, 12))
            
    doc.build(story)
    buffer.seek(0)
    return buffer

def upload_to_s3(file_obj, bucket, key):
    s3 = get_boto3_client("s3")
    file_obj.seek(0)
    s3.upload_fileobj(file_obj, bucket, key)
    return f"s3://{bucket}/{key}"

def update_task_status(task_id, status, report_url=None, state=None, events=None, current_agent=None):
    """Update task status in DynamoDB.
    
    Args:
        task_id: Task identifier
        status: Task status string
        report_url: S3 URL of the final report
        state: Serialized graph state for resumption
        events: List of structured event dicts from create_agent_event()
        current_agent: Currently active agent name for real-time UI updates
    """
    dynamodb = get_boto3_client("dynamodb")
    
    update_expression = "SET #s = :s"
    expression_attribute_names = {"#s": "status"}
    expression_attribute_values = {":s": {"S": status}}
    
    if events:
        # Store events as JSON strings in DynamoDB list
        update_expression += ", #e = list_append(if_not_exists(#e, :empty_list), :e)"
        expression_attribute_names["#e"] = "events"
        expression_attribute_values[":e"] = {"L": [{"S": json.dumps(e)} for e in events]}
        expression_attribute_values[":empty_list"] = {"L": []}
        
    if report_url:
        update_expression += ", #r = :r"
        expression_attribute_names["#r"] = "report_url"
        expression_attribute_values[":r"] = {"S": report_url}
        
    if state:
        update_expression += ", #st = :st"
        expression_attribute_names["#st"] = "state"
        expression_attribute_values[":st"] = {"S": state}
    
    if current_agent:
        update_expression += ", #ca = :ca"
        expression_attribute_names["#ca"] = "current_agent"
        expression_attribute_values[":ca"] = {"S": current_agent}
        
    dynamodb.update_item(
        TableName=settings.DYNAMODB_TABLE_TASKS,
        Key={"task_id": {"S": task_id}},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )

def serialize_state(state):
    """Serialize ResearchState to a JSON string."""
    state_copy = state.copy()
    if 'messages' in state_copy:
        state_copy['messages'] = messages_to_dict(state_copy['messages'])
    return json.dumps(state_copy)

def deserialize_state(json_str):
    """Deserialize JSON string back to ResearchState."""
    data = json.loads(json_str)
    if 'messages' in data:
        data['messages'] = messages_from_dict(data['messages'])
    return data

