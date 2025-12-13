from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional
import operator
from langchain_core.messages import AnyMessage

class ResearchState(TypedDict):
    task: str
    date: str
    plan: List[str]
    financial_data: Annotated[Dict[str, Any], operator.ior]
    market_intelligence: Annotated[List[str], operator.add]
    competitor_benchmarks: Annotated[List[str], operator.add]
    clarification_question: Optional[str]
    draft_report: str
    critique: str
    messages: Annotated[List[AnyMessage], operator.add]
    revision_count: int
    next_step: str
