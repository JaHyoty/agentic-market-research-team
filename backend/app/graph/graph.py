from langgraph.graph import StateGraph, END
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
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Add edges
    # Logic: Supervisor decides where to go.
    # For this prototype, we will use conditional edges based on the supervisor's output
    # But since my supervisor_node currently returns messages, I need a router function.
    
    def supervisor_router(state):
        # This logic should match what the supervisor_node decided
        # In a real app, supervisor_node would output a structured decision
        # Here we check state again or check the last message
        
        has_financials = bool(state.get('financial_data'))
        has_market = bool(state.get('market_intelligence'))
        has_competitors = bool(state.get('competitor_benchmarks'))
        
        if not has_financials:
            return "quant"
        if not has_market:
            return "researcher"
        if not has_competitors:
            return "scout"
        
        # If we have the draft, go to reviewer
        if state.get('draft_report'):
            # If reviewer approved, end
            if "APPROVE" in state.get('critique', ''):
                return END
            # If reviewer rejected, back to writer (or supervisor)
            if "REVISE" in state.get('critique', ''):
                return "writer"
            # If we have draft but no critique, go to reviewer
            return "reviewer"
            
        # If we have all data but no draft, go to writer
        return "writer"

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "quant": "quant",
            "researcher": "researcher",
            "scout": "scout",
            "writer": "writer",
            "reviewer": "reviewer",
            END: END
        }
    )
    
    # Workers go back to supervisor
    workflow.add_edge("quant", "supervisor")
    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("scout", "supervisor")
    
    # Writer goes to supervisor (which will route to reviewer)
    workflow.add_edge("writer", "supervisor")
    
    # Reviewer goes to supervisor (which will route to END or back to Writer)
    workflow.add_edge("reviewer", "supervisor")
    
    return workflow.compile()
