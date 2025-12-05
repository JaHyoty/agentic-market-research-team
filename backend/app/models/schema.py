from pydantic import BaseModel
from typing import Optional, List

class ResearchRequest(BaseModel):
    query: str
    
class ResearchResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: List[str]
    report_url: Optional[str] = None
