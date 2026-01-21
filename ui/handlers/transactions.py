"""
Transaction handlers for Gradio UI.
"""

import pandas as pd

from services import PortfolioService


def handle_add_transaction(date: str, ticker: str, qty: float, tax_rate: float, notes: str) -> tuple[str, pd.DataFrame]:
    """Handle adding a new transaction. Price is auto-fetched from TEFAS."""
    return PortfolioService.add_transaction(date, ticker, qty, tax_rate, notes)


def handle_delete_transaction(transaction_id: int) -> tuple[str, pd.DataFrame]:
    """Handle deleting a transaction."""
    return PortfolioService.delete_transaction(transaction_id)


def refresh_portfolio() -> pd.DataFrame:
    """Refresh the portfolio table."""
    return PortfolioService.get_portfolio()


def handle_refresh_tefas_prices() -> tuple[str, pd.DataFrame]:
    """Refresh TEFAS prices for all tickers in portfolio."""
    return PortfolioService.refresh_tefas_prices()


def get_ticker_price_table() -> pd.DataFrame:
    """Generate a table with tickers for price entry, auto-filled from TEFAS data."""
    return PortfolioService.get_ticker_price_table()


def get_unique_tickers() -> list[str]:
    """Get list of unique tickers in portfolio."""
    return PortfolioService.get_unique_tickers()
