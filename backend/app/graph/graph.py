from langgraph.graph import StateGraph, END
import re
from langgraph.prebuilt import ToolNode, tools_condition
from backend.app.tools.search import search_web
from backend.app.tools.web import scrape_website
from backend.app.tools.finance import get_stock_price, get_financial_metrics
from backend.app.models.state import ResearchState
from backend.app.agents.nodes import (
    supervisor_node,
    quant_node,
    researcher_node,
    scout_node,
    writer_node,
    reviewer_node
)

def create_graph():
    workflow = StateGraph(ResearchState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("quant", quant_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("scout", scout_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("reviewer", reviewer_node)
    
    # Tool Nodes
    workflow.add_node("researcher_tools", ToolNode([search_web, scrape_website]))
    workflow.add_node("scout_tools", ToolNode([search_web, scrape_website]))
    workflow.add_node("quant_tools", ToolNode([search_web, scrape_website, get_stock_price, get_financial_metrics]))
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add edges
    def supervisor_router(state):
        next_step = state.get('next_step')
        if next_step == "ask_question":
            return END
        if next_step == "FINISH":
            if state.get("revision_count", 0) >= 3:
                return END
            return "reviewer" # We want reviewer to handle the final approval
        return next_step

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "quant": "quant",
            "researcher": "researcher",
            "scout": "scout",
            "writer": "writer",
            "reviewer": "reviewer",
            "supervisor": "supervisor",
            END: END
        }
    )
    
    # Workers go back to supervisor
    workflow.add_edge("quant", "supervisor")
    
    # Researcher Loop
    workflow.add_conditional_edges(
        "researcher",
        tools_condition,
        {"tools": "researcher_tools", END: "supervisor"}
    )
    workflow.add_edge("researcher_tools", "researcher")
    
    # Scout Loop
    workflow.add_conditional_edges(
        "scout",
        tools_condition,
        {"tools": "scout_tools", END: "supervisor"}
    )
    workflow.add_edge("scout_tools", "scout")
    
    # Quant Loop
    workflow.add_conditional_edges(
        "quant",
        tools_condition,
        {"tools": "quant_tools", END: "supervisor"}
    )
    workflow.add_edge("quant_tools", "quant")
    
    # Writer goes to supervisor (which will route to reviewer)
    workflow.add_edge("writer", "supervisor")
    
    # Reviewer Router
    def reviewer_router(state):
        pattern = r'\b' + re.escape("APPROVE") + r'\b'
        if re.search(pattern, state.get('critique', ''), re.IGNORECASE):
            return "FINISH"
        return "REVISE"

    workflow.add_conditional_edges(
        "reviewer",
        reviewer_router,
        {
            "FINISH": END,
            "REVISE": "supervisor"
        }
    )
    
    return workflow.compile()
