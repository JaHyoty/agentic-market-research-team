import yfinance as yf
from langchain_core.tools import tool
import json

@tool
def get_stock_price(ticker: str):
    """Get the current stock price and basic info for a ticker."""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        return json.dumps({
            "symbol": info.get("symbol"),
            "currentPrice": info.get("currentPrice"),
            "marketCap": info.get("marketCap"),
            "peRatio": info.get("trailingPE"),
            "sector": info.get("sector")
        })
    except Exception as e:
        return f"Error fetching data for {ticker}: {str(e)}"

@tool
def get_financial_metrics(ticker: str):
    """Get financial metrics like revenue and margins."""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        return json.dumps({
            "revenueGrowth": info.get("revenueGrowth"),
            "grossMargins": info.get("grossMargins"),
            "operatingMargins": info.get("operatingMargins"),
            "ebitda": info.get("ebitda")
        })
    except Exception as e:
        return f"Error fetching metrics for {ticker}: {str(e)}"
