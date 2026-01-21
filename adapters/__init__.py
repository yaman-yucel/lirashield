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

from adapters.yfinance_stocks import (
    fetch_stock_prices,
    update_stock_prices,
    fetch_prices_for_new_stock,
    get_current_stock_price,
    is_valid_stock,
    get_stock_info,
)

__all__ = [
    # TEFAS
    "fetch_fund_prices",
    "update_fund_prices",
    "fetch_prices_for_new_ticker",
    "get_current_price",
    "is_valid_tefas_fund",
    # yfinance stocks
    "fetch_stock_prices",
    "update_stock_prices",
    "fetch_prices_for_new_stock",
    "get_current_stock_price",
    "is_valid_stock",
    "get_stock_info",
]
