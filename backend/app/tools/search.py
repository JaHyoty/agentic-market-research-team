from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool

@tool
def search_web(query: str, max_results: int = 10):
    """Search the web for information using Tavily."""
    tool = TavilySearchResults(max_results=max_results)
    return tool.invoke({"query": query})
