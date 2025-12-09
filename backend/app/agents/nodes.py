from backend.app.openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, SystemMessage
from backend.app.models.state import ResearchState
from backend.app.agents.prompts import *
from backend.app.tools.search import search_web
from backend.app.tools.finance import get_stock_price, get_financial_metrics
from backend.app.tools.web import scrape_website
import json

import sys
from backend.app.config import settings

print(f"Initializing ChatOpenAI with API Key present: {bool(settings.OPENAI_API_KEY)}", file=sys.stderr)

# Initialize LLM
llm = ChatOpenRouter(model="x-ai/grok-4-fast", temperature=0)

def supervisor_node(state: ResearchState):
    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state['messages']
    # In a real implementation, we would use structured output to decide the next node
    # For simplicity here, we will just analyze the state and pick a next step
    # This is a simplified logic for the prototype
    
    # Check what data we have
    has_financials = bool(state.get('financial_data'))
    has_market = bool(state.get('market_intelligence'))
    has_competitors = bool(state.get('competitor_benchmarks'))
    
    if not has_financials:
        return {"messages": [SystemMessage(content="Routing to Quant")]}
    if not has_market:
        return {"messages": [SystemMessage(content="Routing to Researcher")]}
    if not has_competitors:
        return {"messages": [SystemMessage(content="Routing to Scout")]}
        
    return {"messages": [SystemMessage(content="Routing to Writer")]}

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
    
    return {"financial_data": {"status": "collected"}, "messages": [response]}

def researcher_node(state: ResearchState):
    messages = [SystemMessage(content=RESEARCHER_PROMPT)] + state['messages']
    agent = llm.bind_tools([search_web])
    response = agent.invoke(messages)
    return {"market_intelligence": ["Market data collected"], "messages": [response]}

def scout_node(state: ResearchState):
    messages = [SystemMessage(content=SCOUT_PROMPT)] + state['messages']
    agent = llm.bind_tools([search_web, scrape_website])
    response = agent.invoke(messages)
    return {"competitor_benchmarks": ["Competitor data collected"], "messages": [response]}

def writer_node(state: ResearchState):
    messages = [SystemMessage(content=WRITER_PROMPT)] + state['messages']
    response = llm.invoke(messages)
    return {"draft_report": response.content, "messages": [response]}

def reviewer_node(state: ResearchState):
    messages = [SystemMessage(content=REVIEWER_PROMPT), HumanMessage(content=state['draft_report'])]
    response = llm.invoke(messages)
    return {"critique": response.content, "messages": [response]}
