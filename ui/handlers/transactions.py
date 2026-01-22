"""
Transaction handlers for Gradio UI.
"""

import pandas as pd

from core.database import ASSET_TEFAS, ASSET_USD_STOCK, ASSET_CASH, TX_BUY, TX_SELL
from services import PortfolioService


def handle_add_transaction(date: str, ticker: str, qty: float, tax_rate: float, notes: str, asset_type: str, transaction_type: str = "Buy", buy_price: float | None = None) -> tuple[str, pd.DataFrame]:
    """Handle adding a new transaction (buy or sell). Price can be manually entered or auto-fetched."""
    # Map UI labels to asset type constants
    asset_type_map = {
        "TEFAS Fund (TRY)": ASSET_TEFAS,
        "US Stock (USD)": ASSET_USD_STOCK,
        "Cash (TRY)": ASSET_CASH,
        "Cash (USD)": ASSET_CASH,
    }

    # Map UI labels to transaction type constants
    tx_type_map = {
        "Buy": TX_BUY,
        "Sell": TX_SELL,
    }

    mapped_asset_type = asset_type_map.get(asset_type, ASSET_TEFAS)
    mapped_tx_type = tx_type_map.get(transaction_type, TX_BUY)

    # For cash, set the ticker to the currency
    if "Cash (TRY)" in asset_type:
        ticker = "TRY"
    elif "Cash (USD)" in asset_type:
        ticker = "USD"

    # Convert buy_price: if None or 0, pass None; otherwise pass the value
    price = float(buy_price) if buy_price is not None and buy_price > 0 else None

    return PortfolioService.add_transaction(date, ticker, qty, tax_rate, notes, mapped_asset_type, mapped_tx_type, price)


def handle_delete_transaction(transaction_id: int) -> tuple[str, pd.DataFrame]:
    """Handle deleting a transaction."""
    return PortfolioService.delete_transaction(transaction_id)


def refresh_portfolio(ticker: str | None = None) -> pd.DataFrame:
    """Refresh the portfolio table.

    Args:
        ticker: Optional ticker symbol to filter by. If None or empty, returns all transactions.

    Returns:
        DataFrame with portfolio transactions, optionally filtered by ticker.
    """
    if ticker and ticker.strip():
        return PortfolioService.get_portfolio(ticker.strip())
    return PortfolioService.get_portfolio()


def handle_refresh_prices() -> tuple[str, pd.DataFrame]:
    """Refresh prices for all tickers in portfolio (TEFAS and US stocks)."""
    return PortfolioService.refresh_prices()


def handle_refresh_tefas_prices() -> tuple[str, pd.DataFrame]:
    """Refresh prices for all tickers in portfolio."""
    return PortfolioService.refresh_prices()


def get_ticker_price_table() -> pd.DataFrame:
    """Generate a table with tickers for price entry, auto-filled from price data."""
    return PortfolioService.get_ticker_price_table()


def get_unique_tickers() -> list[str]:
    """Get list of unique tickers in portfolio."""
    return PortfolioService.get_unique_tickers()
