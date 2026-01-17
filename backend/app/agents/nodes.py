from backend.app.openrouter import ChatOpenRouter
from langchain_core.messages import HumanMessage, SystemMessage
from backend.app.models.state import ResearchState
from backend.app.agents.prompts import *
from backend.app.tools.search import search_web
from backend.app.tools.finance import get_stock_price, get_financial_metrics
from backend.app.tools.web import scrape_website
from backend.app.utils import parse_response_content
from backend.app.config import settings
import re
import json
import sys

print(f"Initializing ChatOpenRouter with API Key present: {bool(settings.OPENROUTER_API_KEY)}", file=sys.stderr)

# Initialize LLM
llm = ChatOpenRouter(
    model="x-ai/grok-4-fast",
    temperature=0
)

def supervisor_node(state: ResearchState):
    # check if revision limit reached
    if state.get("revision_count", 0) >= 3:
        print("Supervisor: Revision limit (3) reached. Ending graph.", file=sys.stderr)
        return {"next_step": "FINISH", "messages": []}
    
    # Construct context from state data instead of raw messages
    context = f"Task: {state.get('task')}\n\n"
    
    context += f"Financial Data: {json.dumps(state.get('financial_data', 'No financial data collected'))}\n\n"
    context += f"Market Intelligence: {state.get('market_intelligence', 'No market intelligence collected')}\n\n"
    context += f"Competitor Benchmarks: {state.get('competitor_benchmarks', 'No competitor benchmarks collected')}\n\n"
    context += f"Draft Report: {state.get('draft_report', 'No draft report generated')}\n\n"
    
    if state.get('draft_report'):
        context += f"Reviewer Critique: {state.get('critique', 'No critique on draft report provided')}\n"
    
    # Invoke LLM with context
    messages = [
        SystemMessage(content=SUPERVISOR_PROMPT),
        HumanMessage(content=context)
    ]
    response = llm.invoke(messages)
    
    # Parse response content
    decision = parse_response_content(response.content).strip()
    
    # Basic validation/cleanup of the decision
    valid_steps = ["reviewer", "writer", "quant", "researcher", "scout", "FINISH"]
    
    # Use regex to find whole words to avoid partial matches (e.g. "quant" in "Quantification")
    next_step = None
    
    # Priority 0: Check for ask_question (handles multiple formats)
    # Format 1: "ask_question: What is X?"
    # Format 2: "ask_question\nWhat is X?"
    # Format 3: Just "ask_question" followed by content
    if "ask_question" in decision.lower():
        # Try to extract the question
        question = ""
        
        # Try colon separator first
        if ":" in decision:
            parts = decision.split(":", 1)
            if "ask_question" in parts[0].lower():
                question = parts[1].strip()
        
        # Try newline separator
        if not question and "\n" in decision:
            lines = decision.split("\n", 1)
            if "ask_question" in lines[0].lower() and len(lines) > 1:
                question = lines[1].strip()
        
        # Default question if we couldn't extract one
        if not question:
            question = "Could you please clarify your research objective?"
        
        next_step = "ask_question"
        print(f"Supervisor Decision: ASK QUESTION -> {question}", file=sys.stderr)
        response.name = "supervisor"
        return {
            "next_step": next_step, 
            "clarification_question": question,
            "messages": [response]
        }

    # Priority 1: Check for exact match after stripping (most reliable)
    clean_decision = decision.strip().lower()
    for step in valid_steps:
        if clean_decision == step.lower():
            next_step = step if step != "FINISH" else "FINISH"
            break
            
    # Priority 2: Check for step followed by a colon (e.g., "quant: do this")
    if not next_step:
        for step in valid_steps:
            pattern = r'\b' + re.escape(step) + r':\s*'
            if re.search(pattern, decision, re.IGNORECASE):
                next_step = step if step != "FINISH" else "FINISH"
                break
            
    # Priority 3: Check for whole word step if no exact match or colon pattern (e.g., "I choose quant")
    if not next_step:
        for step in valid_steps:
            pattern = r'\b' + re.escape(step) + r'\b'
            if re.search(pattern, decision, re.IGNORECASE):
                next_step = step if step != "FINISH" else "FINISH"
                break
            
    # Default fallback
    if not next_step:
        print(f"Supervisor Warning: Could not parse decision '{decision[:50]}...'. Defaulting to 'supervisor'.", file=sys.stderr)
        next_step = "supervisor"
        
    print(f"Supervisor Decision: {next_step}", file=sys.stderr)
    
    # We add the supervisor's decision to the message history for transparency.
    response.name = "supervisor"
    return {"next_step": next_step, "messages": [response]}

def quant_node(state: ResearchState):
    # Construct context
    context = f""

    # Add existing financial data if any
    if state.get('financial_data'):
        context += f"Existing Financial Data: {state.get('financial_data')}\n\n"
    
    # Add Supervisor Instructions (Last Message)
    last_message = state.get('messages', [])[-1] if state.get('messages') else None
    if last_message:
        sender = last_message.name if hasattr(last_message, 'name') and last_message.name else "Supervisor"
        context += f"Instructions from {sender}: {last_message.content}\n"
    
    messages = [
        SystemMessage(content=QUANT_PROMPT),
        HumanMessage(content=context)
    ]

    # Bind tools to LLM and call the agent
    tools = [search_web, scrape_website, get_stock_price, get_financial_metrics]
    agent = llm.bind_tools(tools)
    response = agent.invoke(messages)
    
    response.name = "quant"
    
    # If it's a tool call, just pass the message
    if response.tool_calls:
        return {"messages": [response]}
        
    # Final answer: extract content and update state
    content = parse_response_content(response.content)
    # Since financial_data is a dict, we wrap the text content. 
    # Ideal implementation would parse JSON, but text report is fine for now.
    return {
        "financial_data": {"report": content}, 
        "messages": [response]
    }

def researcher_node(state: ResearchState):
    # Construct context from state data
    context = f"Task: {state.get('task')}\n\n"

    # Add existing market intelligence if any
    if state.get('market_intelligence'):
        context += f"Existing Market Intelligence: {state.get('market_intelligence')}\n\n"
    
    # Add Supervisor Instructions (Last Message) - REMOVED from context, will be in history
    
    # Filter for relevant history (since last Supervisor message)
    state_messages = state.get('messages', [])
    start_index = 0
    for i in range(len(state_messages) - 1, -1, -1):
        m = state_messages[i]
        if getattr(m, 'name', '') == 'supervisor':
            start_index = i
            break
            
    recent_history = state_messages[start_index:] if state_messages else []

    messages = [
        SystemMessage(content=RESEARCHER_PROMPT + "\n\n" + context),
    ] + recent_history
    
    agent = llm.bind_tools([search_web, scrape_website])
    response = agent.invoke(messages)
    
    response.name = "researcher"
    
    if response.tool_calls:
        return {"messages": [response]}
        
    content = parse_response_content(response.content)
    return {
        "market_intelligence": [content], 
        "messages": [response]
    }

def scout_node(state: ResearchState):    
    # Construct context
    context = f""
    
    # Add existing competitor benchmarks if any
    if state.get('competitor_benchmarks'):
        context += f"Existing Competitor Benchmarks: {state.get('competitor_benchmarks')}\n\n"
    
    # Add Supervisor Instructions (Last Message) - REMOVED from context, will be in history
    
    # Filter for relevant history (since last Supervisor message)
    state_messages = state.get('messages', [])
    start_index = 0
    for i in range(len(state_messages) - 1, -1, -1):
        m = state_messages[i]
        if getattr(m, 'name', '') == 'supervisor':
            start_index = i
            break
            
    recent_history = state_messages[start_index:] if state_messages else []

    messages = [
        SystemMessage(content=SCOUT_PROMPT + "\n\n" + context),
    ] + recent_history
    
    agent = llm.bind_tools([search_web, scrape_website])
    response = agent.invoke(messages)
    
    response.name = "scout"
    
    if response.tool_calls:
        return {"messages": [response]}
        
    content = parse_response_content(response.content)
    return {
        "competitor_benchmarks": [content], 
        "messages": [response]
    }

def writer_node(state: ResearchState):
    # Construct context from state data
    context = f"Task: {state.get('task')}\n\n"
    
    context += f"Financial Data: {json.dumps(state.get('financial_data', 'No financial data collected'))}\n\n"
    context += f"Market Intelligence: {state.get('market_intelligence', 'No market intelligence collected')}\n\n"
    context += f"Competitor Benchmarks: {state.get('competitor_benchmarks', 'No competitor benchmarks collected')}\n\n"
    if state.get('critique'):
        context += f"Critique from reviewer on previous draft: {state.get('critique')}\n\n"

    # Add Supervisor Instructions (Last Message)
    last_message = state.get('messages', [])[-1] if state.get('messages') else None
    if last_message:
        sender = last_message.name if hasattr(last_message, 'name') and last_message.name else "Supervisor"
        context += f"{sender} Instructions from supervisor: {last_message.content}\n"
    
    messages = [
        SystemMessage(content=WRITER_PROMPT),
        HumanMessage(content=context)
    ]
    
    response = llm.invoke(messages)
    content = parse_response_content(response.content)
    response.name = "writer"
    revision_count = state.get("revision_count", 0) + 1
    return {"draft_report": content, "critique": "", "messages": [response], "revision_count": revision_count}

def reviewer_node(state: ResearchState):
    messages = [
        SystemMessage(content=REVIEWER_PROMPT), 
        HumanMessage(content=f"Original Task & Clarifications:\n{state.get('task')}\n\nDraft Report to Review:\n{state.get('draft_report', 'No report drafted.')}")
    ]
    
    response = llm.invoke(messages)
    content = parse_response_content(response.content)
    response.name = "reviewer"
    return {"critique": content, "messages": [response]}
