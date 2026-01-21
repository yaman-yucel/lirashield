"""
Chart handlers for Gradio UI.
"""

import plotly.graph_objects as go

from services import ChartsService


def generate_fund_chart(ticker: str, base_date: str | None = None) -> tuple[go.Figure | None, str]:
    """
    Generate a dual-axis chart showing fund price in both TRY and USD terms.

    Args:
        ticker: Fund ticker symbol
        base_date: Optional start date to filter data from (YYYY-MM-DD)

    Returns:
        Tuple of (plotly figure, status message)
    """
    return ChartsService.generate_fund_chart(ticker, base_date)


def generate_normalized_chart(tickers_str: str, show_usd: bool, base_date: str | None = None) -> tuple[go.Figure | None, str]:
    """
    Generate a normalized comparison chart for multiple funds.
    All funds are normalized to 100 at the base date for easy comparison.

    Args:
        tickers_str: Comma-separated list of tickers
        show_usd: Whether to show USD-denominated values
        base_date: Optional base date for normalization (YYYY-MM-DD)

    Returns:
        Tuple of (plotly figure, status message)
    """
    return ChartsService.generate_normalized_chart(tickers_str, show_usd, base_date)
