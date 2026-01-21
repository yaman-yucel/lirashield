"""
UI Handlers - thin wrappers around services for Gradio event handling.
"""

from ui.handlers.transactions import (
    handle_add_transaction,
    handle_delete_transaction,
    refresh_portfolio,
    handle_refresh_tefas_prices,
    handle_refresh_prices,
    get_ticker_price_table,
    get_unique_tickers,
)
from ui.handlers.rates import (
    handle_add_rate,
    handle_delete_rate,
    handle_fetch_rate,
    handle_bulk_import,
    refresh_rates,
    handle_refresh_all_usd_rates,
    handle_quick_refresh_usd_rates,
    handle_add_cpi,
    handle_delete_cpi,
    handle_bulk_import_cpi,
    refresh_cpi,
)
from ui.handlers.charts import (
    generate_fund_chart,
    generate_normalized_chart,
)
from ui.handlers.analysis import (
    analyze_portfolio,
)
from ui.handlers.refresh import (
    handle_refresh_cpi_csv,
    handle_quick_check_usdtry,
    handle_long_check_usdtry,
    handle_quick_check_us_stocks,
    handle_long_check_us_stocks,
    handle_quick_check_tefas,
    handle_long_check_tefas,
)

__all__ = [
    # Transaction handlers
    "handle_add_transaction",
    "handle_delete_transaction",
    "refresh_portfolio",
    "handle_refresh_tefas_prices",
    "handle_refresh_prices",
    "get_ticker_price_table",
    "get_unique_tickers",
    # Rate handlers
    "handle_add_rate",
    "handle_delete_rate",
    "handle_fetch_rate",
    "handle_bulk_import",
    "refresh_rates",
    "handle_refresh_all_usd_rates",
    "handle_quick_refresh_usd_rates",
    "handle_add_cpi",
    "handle_delete_cpi",
    "handle_bulk_import_cpi",
    "refresh_cpi",
    # Chart handlers
    "generate_fund_chart",
    "generate_normalized_chart",
    # Analysis handlers
    "analyze_portfolio",
    # Refresh handlers
    "handle_refresh_cpi_csv",
    "handle_quick_check_usdtry",
    "handle_long_check_usdtry",
    "handle_quick_check_us_stocks",
    "handle_long_check_us_stocks",
    "handle_quick_check_tefas",
    "handle_long_check_tefas",
]
