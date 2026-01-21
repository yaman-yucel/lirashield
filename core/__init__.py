"""
Core modules for database and analysis operations.
"""

from core.database import (
    get_connection,
    init_db,
    # Transaction functions
    add_transaction,
    get_portfolio,
    get_portfolio_raw,
    get_unique_tickers,
    delete_transaction,
    # CPI/USD rate functions
    add_cpi_usd_rate,
    get_cpi_usd_rates,
    get_cpi_usd_rate_for_date,
    delete_cpi_usd_rate,
    bulk_import_cpi_usd_rates,
    # Official CPI functions
    add_cpi_official,
    get_cpi_official_data,
    delete_cpi_official,
    bulk_import_cpi_official,
    calculate_cumulative_cpi,
    calculate_cumulative_cpi_daily,
    get_cpi_mom_for_month,
    get_latest_cpi_mom,
    # Fund price functions
    add_fund_price,
    bulk_add_fund_prices,
    get_fund_prices,
    get_latest_fund_price,
    get_fund_price_for_date,
    get_oldest_fund_price_date,
    get_fund_price_date_range,
    get_all_fund_latest_prices,
)

from core.analysis import (
    fetch_usd_rate_from_yfinance,
    get_usd_rate,
    calculate_real_return,
    calculate_portfolio_summary,
    fetch_usd_rates_for_date_range,
    fetch_all_usd_rates,
    fetch_missing_usd_rates,
    get_usd_rates_as_dataframe,
)

__all__ = [
    # Database
    "get_connection",
    "init_db",
    "add_transaction",
    "get_portfolio",
    "get_portfolio_raw",
    "get_unique_tickers",
    "delete_transaction",
    "add_cpi_usd_rate",
    "get_cpi_usd_rates",
    "get_cpi_usd_rate_for_date",
    "delete_cpi_usd_rate",
    "bulk_import_cpi_usd_rates",
    "add_cpi_official",
    "get_cpi_official_data",
    "delete_cpi_official",
    "bulk_import_cpi_official",
    "calculate_cumulative_cpi",
    "calculate_cumulative_cpi_daily",
    "get_cpi_mom_for_month",
    "get_latest_cpi_mom",
    "add_fund_price",
    "bulk_add_fund_prices",
    "get_fund_prices",
    "get_latest_fund_price",
    "get_fund_price_for_date",
    "get_oldest_fund_price_date",
    "get_fund_price_date_range",
    "get_all_fund_latest_prices",
    # Analysis
    "fetch_usd_rate_from_yfinance",
    "get_usd_rate",
    "calculate_real_return",
    "calculate_portfolio_summary",
    "fetch_usd_rates_for_date_range",
    "fetch_all_usd_rates",
    "fetch_missing_usd_rates",
    "get_usd_rates_as_dataframe",
]
