"""
Analysis handlers for Gradio UI.
"""

import pandas as pd

from services import AnalysisService


def analyze_portfolio(price_table_df: pd.DataFrame, auto_fetch: bool) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Analyze portfolio with current prices and calculate real returns.

    Args:
        price_table_df: DataFrame with Ticker and Current Price columns
        auto_fetch: Whether to auto-fetch missing USD rates from yfinance

    Returns:
        Tuple of (details_table, summary_table, status_message)
    """
    return AnalysisService.analyze_portfolio(price_table_df, auto_fetch)
