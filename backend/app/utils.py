import boto3
from backend.app.config import settings
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import markdown
import io

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
    s3.upload_fileobj(file_obj, bucket, key)
    return f"s3://{bucket}/{key}"

def update_task_status(task_id, status, progress=None, report_url=None):
    dynamodb = get_boto3_client("dynamodb")
    
    update_expression = "SET #s = :s"
    expression_attribute_names = {"#s": "status"}
    expression_attribute_values = {":s": {"S": status}}
    
    if progress:
        update_expression += ", #p = list_append(if_not_exists(#p, :empty_list), :p)"
        expression_attribute_names["#p"] = "progress"
        expression_attribute_values[":p"] = {"L": [{"S": p} for p in progress]}
        expression_attribute_values[":empty_list"] = {"L": []}
        
    if report_url:
        update_expression += ", #r = :r"
        expression_attribute_names["#r"] = "report_url"
        expression_attribute_values[":r"] = {"S": report_url}
        
    dynamodb.update_item(
        TableName=settings.DYNAMODB_TABLE_TASKS,
        Key={"task_id": {"S": task_id}},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
