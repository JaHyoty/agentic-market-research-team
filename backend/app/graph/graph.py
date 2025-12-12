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
    def supervisor_router(state):
        next_step = state.get('next_step')
        if next_step == "FINISH":
            return END
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
    workflow.add_edge("researcher", "supervisor")
    workflow.add_edge("scout", "supervisor")
    
    # Writer goes to supervisor (which will route to reviewer)
    workflow.add_edge("writer", "supervisor")
    
    # Reviewer goes to supervisor (which will route to END or back to Writer)
    workflow.add_edge("reviewer", "supervisor")
    
    return workflow.compile()
