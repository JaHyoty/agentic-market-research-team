from backend.app.openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, SystemMessage
from backend.app.models.state import ResearchState
from backend.app.agents.prompts import *
from backend.app.tools.search import search_web
from backend.app.tools.finance import get_stock_price, get_financial_metrics
from backend.app.tools.web import scrape_website
from backend.app.utils import parse_response_content
import re
import json

import sys
from backend.app.config import settings

print(f"Initializing ChatOpenRouter with API Key present: {bool(settings.OPENROUTER_API_KEY)}", file=sys.stderr)

# Initialize LLM
llm = ChatOpenRouter(
    model="x-ai/grok-4-fast",
    temperature=0,
    reasoning={
        "exclude": True
    }
)

def supervisor_node(state: ResearchState):
    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state['messages']
    response = llm.invoke(messages)
    decision = parse_response_content(response.content).strip()
    
    # Basic validation/cleanup of the decision
    valid_steps = ["quant", "researcher", "scout", "writer", "reviewer", "FINISH"]
    
    # Use regex to find whole words to avoid partial matches (e.g. "quant" in "Quantification")
    next_step = None
    
    # Priority 1: Check for exact match after stripping (most reliable)
    clean_decision = decision.strip().lower()
    for step in valid_steps:
        if clean_decision == step.lower():
            next_step = step if step != "FINISH" else "FINISH"
            break
            
    # Priority 2: Check boundaries if no exact match (e.g. "I choose quant")
    if not next_step:
        for step in valid_steps:
            pattern = r'\b' + re.escape(step) + r'\b'
            if re.search(pattern, decision, re.IGNORECASE):
                next_step = step if step != "FINISH" else "FINISH"
                break
            
    if not next_step:
        # Default fallback
        print(f"Supervisor Warning: Could not parse decision '{decision}'. Defaulting to 'supervisor'.", file=sys.stderr)
        next_step = "supervisor"
        
    print(f"Supervisor Decision: {next_step} (Raw: {decision[:100]}...)", file=sys.stderr)
    
    # We add the supervisor's decision to the message history for transparency.
    response.name = "supervisor"
    return {"next_step": next_step, "messages": [response]}

def quant_node(state: ResearchState):
    messages = [SystemMessage(content=QUANT_PROMPT)] + state['messages']
    # Bind tools
    tools = [get_stock_price, get_financial_metrics]
    agent = llm.bind_tools(tools)
    response = agent.invoke(messages)
    
    # Execute tools (simplified for prototype, normally we'd loop)
    # Here we assume the LLM calls a tool, we execute it, and update state
    # For the sake of this implementation, let's assume we extract the ticker from the task
    # and just fetch data.
    
    # A better way is to use the prebuilt create_react_agent or similar, but we are building nodes manually.
    # Let's just use the LLM to decide what to call, and if it calls a tool, we execute it.
    
    # To make this robust without a full tool loop in this node, we can just ask the LLM to generate the data
    # or we can use a tool-calling agent executor.
    
    # Let's try to extract ticker from task
    task = state['task']
    # Simple heuristic: look for uppercase words that might be tickers
    # This is very basic.
    
    response.content = parse_response_content(response.content)
    response.name = "quant"
    return {"financial_data": {"status": "collected"}, "messages": [response]}

def researcher_node(state: ResearchState):
    messages = [SystemMessage(content=RESEARCHER_PROMPT)] + state['messages']
    agent = llm.bind_tools([search_web])
    response = agent.invoke(messages)
    response.content = parse_response_content(response.content)
    response.name = "researcher"
    return {"market_intelligence": ["Market data collected"], "messages": [response]}

def scout_node(state: ResearchState):
    messages = [SystemMessage(content=SCOUT_PROMPT)] + state['messages']
    agent = llm.bind_tools([search_web, scrape_website])
    response = agent.invoke(messages)
    response.content = parse_response_content(response.content)
    response.name = "scout"
    return {"competitor_benchmarks": ["Competitor data collected"], "messages": [response]}

def writer_node(state: ResearchState):
    messages = [SystemMessage(content=WRITER_PROMPT)] + state['messages']
    response = llm.invoke(messages)
    content = parse_response_content(response.content)
    response.name = "writer"
    return {"draft_report": content, "critique": "", "messages": [response]}

def reviewer_node(state: ResearchState):
    messages = [SystemMessage(content=REVIEWER_PROMPT), HumanMessage(content=state['draft_report'])]
    response = llm.invoke(messages)
    content = parse_response_content(response.content)
    response.name = "reviewer"
    return {"critique": content, "messages": [response]}
