from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool

@tool
def search_web(query: str):
    """Search the web for information using Tavily."""
    tool = TavilySearchResults(max_results=5)
    return tool.invoke({"query": query})
