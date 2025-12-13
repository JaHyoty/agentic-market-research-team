from langchain_tavily import TavilySearch
from langchain_core.tools import tool
import sys

@tool
def search_web(query: str, max_results: int = 10):
    """Search the web for information using Tavily."""
    try:
        tool = TavilySearch(max_results=max_results)
        return tool.invoke({"query": query})
    except Exception as e:
        print(f"WARNING: Search tool failed. Error: {e}", file=sys.stderr)
        raise e
