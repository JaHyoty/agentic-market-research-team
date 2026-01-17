from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class ResearchRequest(BaseModel):
    query: str
    
class ResearchResponse(BaseModel):
    task_id: str
    status: str
    message: str

class AgentEvent(BaseModel):
    agent: str
    action: str
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None

class TaskStatus(BaseModel):
    task_id: str
    status: str
    events: List[AgentEvent] = []
    report_url: Optional[str] = None
    query: Optional[str] = None
    created_at: Optional[str] = None
