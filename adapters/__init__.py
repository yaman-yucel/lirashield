"""
Adapters for external APIs (TEFAS, yfinance).
"""

from adapters.tefas import (
    fetch_fund_prices,
    update_fund_prices,
    fetch_prices_for_new_ticker,
    get_current_price,
    is_valid_tefas_fund,
)

__all__ = [
    "fetch_fund_prices",
    "update_fund_prices",
    "fetch_prices_for_new_ticker",
    "get_current_price",
    "is_valid_tefas_fund",
]
