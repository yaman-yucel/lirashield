"""
Refresh handlers for manual data import and API checks.
"""

import pandas as pd
from datetime import datetime, timedelta

from adapters.tefas import update_fund_prices, fetch_fund_prices
from adapters.yfinance_stocks import update_stock_prices, fetch_stock_prices
from core.analysis import fetch_usd_rates_for_date_range
from core.database import (
    get_cpi_usd_rates,
    get_latest_fund_price,
    get_tickers_with_info,
    ASSET_TEFAS,
    ASSET_USD_STOCK,
    bulk_import_cpi_official,
    get_cpi_official_data,
)
from core.log import get_logger

logger = get_logger("refresh")

# ============== CPI CSV IMPORT ==============


def handle_refresh_cpi_csv(csv_text: str) -> tuple[str, pd.DataFrame]:
    """Handle manual CSV import of CPI data."""
    result = bulk_import_cpi_official(csv_text)
    return result, get_cpi_official_data()


# ============== USDTRY RATES ==============


def handle_quick_check_usdtry() -> tuple[str, pd.DataFrame]:
    """
    Quick check: Update USDTRY rates from latest stored date to today.
    """
    from core.database import get_connection

    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(date) FROM cpi_usd_rates")
        latest_date = c.fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")

    if latest_date is None:
        # No rates in database, fetch 5 years
        start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        new_count, msg = fetch_usd_rates_for_date_range(start_date, today)
        status = f"📅 No rates found. Fetched 5 years: {start_date} → {today}\n{msg}"
    else:
        # Fetch from day after latest to today
        start_date = (datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        if start_date > today:
            status = f"✅ Already up to date (latest: {latest_date})"
        else:
            new_count, msg = fetch_usd_rates_for_date_range(start_date, today)
            status = f"📅 Quick check: {start_date} → {today}\n{msg}"

    return status, get_cpi_usd_rates()


def handle_long_check_usdtry() -> tuple[str, pd.DataFrame]:
    """
    Long check: Update USDTRY rates - 5 years if no entry, otherwise from latest date with 5 historical values.
    """
    from core.database import get_connection

    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(date) FROM cpi_usd_rates")
        latest_date = c.fetchone()[0]

    today = datetime.now().strftime("%Y-%m-%d")

    if latest_date is None:
        # No rates in database, fetch 5 years
        start_date = (datetime.now() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        new_count, msg = fetch_usd_rates_for_date_range(start_date, today)
        status = f"📅 No rates found. Fetched 5 years: {start_date} → {today}\n{msg}"
    else:
        # Fetch from 5 years before latest date to today (ensures 5 years of history)
        latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
        start_date = (latest_dt - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        new_count, msg = fetch_usd_rates_for_date_range(start_date, today)
        status = f"📅 Long check: Fetched 5 years from {start_date} → {today}\n{msg}"

    return status, get_cpi_usd_rates()


# ============== US STOCKS ==============


def handle_quick_check_us_stocks() -> tuple[str, pd.DataFrame]:
    """
    Quick check: Update US stock prices from latest stored date to today for each ticker.
    """
    tickers_info = get_tickers_with_info()
    us_stocks = [info for info in tickers_info if info["asset_type"] == ASSET_USD_STOCK]
    logger.info(f"Quick check US stocks: {us_stocks}")
    if not us_stocks:
        return "⚠️ No US stocks found in portfolio", pd.DataFrame()

    results = []
    total_inserted = 0

    for info in us_stocks:
        ticker = info["ticker"]
        inserted, skipped, msg = update_stock_prices(ticker)
        total_inserted += inserted
        results.append(f"{ticker}: {msg}")

    status = "📈 Quick check completed\n" + "\n".join(results)
    return status, pd.DataFrame({"Ticker": [info["ticker"] for info in us_stocks], "Status": results})


def handle_long_check_us_stocks() -> tuple[str, pd.DataFrame]:
    """
    Long check: Update US stock prices - 5 years if no entry, otherwise from latest date with 5 years history.
    """
    tickers_info = get_tickers_with_info()
    us_stocks = [info for info in tickers_info if info["asset_type"] == ASSET_USD_STOCK]

    if not us_stocks:
        return "⚠️ No US stocks found in portfolio", pd.DataFrame()

    results = []
    total_inserted = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for info in us_stocks:
        ticker = info["ticker"]
        latest = get_latest_fund_price(ticker)

        if latest is None:
            # No data exists, fetch 5 years
            inserted, skipped, msg = fetch_stock_prices(ticker, years_back=5, end_date=today)
        else:
            # Fetch from 5 years before latest date to today
            latest_date, _, _ = latest
            latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            start_date = (latest_dt - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
            inserted, skipped, msg = fetch_stock_prices(ticker, start_date=start_date, end_date=today)

        total_inserted += inserted
        results.append(f"{ticker}: {msg}")

    status = "📈 Long check completed (5 years history)\n" + "\n".join(results)
    return status, pd.DataFrame({"Ticker": [info["ticker"] for info in us_stocks], "Status": results})


# ============== TEFAS STOCKS ==============


def handle_quick_check_tefas() -> tuple[str, pd.DataFrame]:
    """
    Quick check: Update TEFAS fund prices from latest stored date to today for each ticker.
    """
    tickers_info = get_tickers_with_info()
    tefas_funds = [info for info in tickers_info if info["asset_type"] == ASSET_TEFAS]

    if not tefas_funds:
        return "⚠️ No TEFAS funds found in portfolio", pd.DataFrame()

    results = []
    total_inserted = 0

    for info in tefas_funds:
        ticker = info["ticker"]
        inserted, skipped, msg = update_fund_prices(ticker)
        total_inserted += inserted
        results.append(f"{ticker}: {msg}")

    status = "📈 Quick check completed\n" + "\n".join(results)
    return status, pd.DataFrame({"Ticker": [info["ticker"] for info in tefas_funds], "Status": results})


def handle_long_check_tefas() -> tuple[str, pd.DataFrame]:
    """
    Long check: Update TEFAS fund prices - 5 years if no entry, otherwise from latest date with 5 years history.
    """
    tickers_info = get_tickers_with_info()
    tefas_funds = [info for info in tickers_info if info["asset_type"] == ASSET_TEFAS]

    if not tefas_funds:
        return "⚠️ No TEFAS funds found in portfolio", pd.DataFrame()

    results = []
    total_inserted = 0
    today = datetime.now().strftime("%Y-%m-%d")

    for info in tefas_funds:
        ticker = info["ticker"]
        latest = get_latest_fund_price(ticker)

        if latest is None:
            # No data exists, fetch 5 years
            inserted, skipped, msg = fetch_fund_prices(ticker, years_back=5, end_date=today)
        else:
            # Fetch from 5 years before latest date to today
            latest_date, _, _ = latest
            latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            start_date = (latest_dt - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
            inserted, skipped, msg = fetch_fund_prices(ticker, start_date=start_date, end_date=today)

        total_inserted += inserted
        results.append(f"{ticker}: {msg}")

    status = "📈 Long check completed (5 years history)\n" + "\n".join(results)
    return status, pd.DataFrame({"Ticker": [info["ticker"] for info in tefas_funds], "Status": results})
