"""
yfinance stock price fetching module.

Fetches historical stock prices from Yahoo Finance for US stocks
and stores them in the database. Uses INSERT OR IGNORE to avoid updating existing records.
"""

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from core.database import (
    CURRENCY_USD,
    bulk_add_fund_prices,
    get_fund_price_date_range,
    get_latest_fund_price,
)


def fetch_stock_prices(
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
    years_back: int = 5,
) -> tuple[int, int, str]:
    """
    Fetch stock prices from Yahoo Finance and store in database.
    Only inserts new records, does not update existing ones.

    Args:
        ticker: Stock ticker symbol (e.g., 'NVDA', 'META', 'BABA', 'QQQ')
        start_date: Start date (YYYY-MM-DD). If None, uses years_back from end_date.
        end_date: End date (YYYY-MM-DD). If None, uses today.
        years_back: How many years back to fetch if start_date is None.

    Returns:
        Tuple of (inserted_count, skipped_count, status_message)
    """
    ticker = ticker.upper().strip()

    # Default end_date to today
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Default start_date to years_back from end_date
    if start_date is None:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=365 * years_back)
        start_date = start_dt.strftime("%Y-%m-%d")

    try:
        # Fetch data from yfinance
        stock = yf.Ticker(ticker)
        data = stock.history(start=start_date, end=end_date, auto_adjust=True)

        if data.empty:
            return 0, 0, f"⚠️ No data found for {ticker} between {start_date} and {end_date}"

        all_prices = []
        for date_idx, row in data.iterrows():
            date_str = date_idx.strftime("%Y-%m-%d")
            # Use Close price
            price = float(row["Close"])
            all_prices.append((date_str, ticker, price))

        if not all_prices:
            return 0, 0, f"⚠️ No data found for {ticker} between {start_date} and {end_date}"

        # Bulk insert all collected prices with USD currency
        inserted, skipped = bulk_add_fund_prices(all_prices, source="yfinance", currency=CURRENCY_USD)

        return inserted, skipped, f"✅ {ticker}: {inserted} new prices added, {skipped} already existed"

    except Exception as e:
        return 0, 0, f"❌ Error fetching {ticker}: {e}"


def update_stock_prices(ticker: str) -> tuple[int, int, str]:
    """
    Update prices for a stock - only fetches missing recent data.
    Checks the latest stored date and fetches from there to today.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Tuple of (inserted_count, skipped_count, status_message)
    """
    ticker = ticker.upper().strip()
    today = datetime.now().strftime("%Y-%m-%d")

    latest = get_latest_fund_price(ticker)

    if latest is None:
        # No data exists, fetch full history
        return fetch_stock_prices(ticker, end_date=today)

    latest_date, _, _ = latest

    # Check if we're already up to date (within last 3 days to account for weekends/holidays)
    days_since_latest = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
    if days_since_latest <= 3:
        return 0, 0, f"✅ {ticker} is up to date (latest: {latest_date})"

    # Fetch from day after latest to today
    start_dt = datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)
    start_date = start_dt.strftime("%Y-%m-%d")

    inserted, skipped, msg = fetch_stock_prices(ticker, start_date=start_date, end_date=today)

    # If no new data found but we have existing data, consider it up to date
    if inserted == 0 and skipped == 0 and "No data found" in msg:
        return 0, 0, f"✅ {ticker} is up to date (latest: {latest_date})"

    return inserted, skipped, msg


def fetch_prices_for_new_stock(ticker: str, transaction_date: str) -> tuple[int, int, str]:
    """
    Fetch historical prices for a newly added stock.
    Fetches from 5 years before the transaction date (or stock inception) to today.

    Args:
        ticker: Stock ticker symbol
        transaction_date: The transaction date (YYYY-MM-DD)

    Returns:
        Tuple of (inserted_count, skipped_count, status_message)
    """
    ticker = ticker.upper().strip()
    today = datetime.now().strftime("%Y-%m-%d")

    # Check if we already have data for this ticker
    existing_range = get_fund_price_date_range(ticker)

    if existing_range:
        oldest, newest = existing_range
        # If transaction date is within existing range or after, just update to today
        if transaction_date >= oldest:
            return update_stock_prices(ticker)
        else:
            # Need to fetch older data before the transaction
            start_dt = datetime.strptime(transaction_date, "%Y-%m-%d") - timedelta(days=365)
            start_date = start_dt.strftime("%Y-%m-%d")
            return fetch_stock_prices(ticker, start_date=start_date, end_date=oldest)

    # No existing data - fetch from 5 years back to today
    tx_dt = datetime.strptime(transaction_date, "%Y-%m-%d")
    start_dt = tx_dt - timedelta(days=365 * 5)
    start_date = start_dt.strftime("%Y-%m-%d")

    return fetch_stock_prices(ticker, start_date=start_date, end_date=today)


def get_current_stock_price(ticker: str) -> float | None:
    """
    Get the most recent price for a stock.
    First tries the database, then fetches from yfinance if not recent enough.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Current price or None if not available
    """
    ticker = ticker.upper().strip()

    latest = get_latest_fund_price(ticker)

    if latest:
        latest_date, price, _ = latest
        # If data is from today or yesterday (markets might be closed), return it
        days_old = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
        if days_old <= 3:  # Allow weekend gap
            return price

    # Try to fetch fresh data
    inserted, _, _ = update_stock_prices(ticker)

    # Get the updated latest price
    latest = get_latest_fund_price(ticker)
    return latest[1] if latest else None


def is_valid_stock(ticker: str) -> bool:
    """
    Check if a ticker is a valid stock by attempting to fetch recent data.

    Args:
        ticker: Stock ticker to validate

    Returns:
        True if valid stock, False otherwise
    """
    try:
        stock = yf.Ticker(ticker.upper().strip())
        info = stock.info
        # Check if we have valid price data
        return info.get("regularMarketPrice") is not None or info.get("previousClose") is not None
    except Exception:
        return False


def get_stock_info(ticker: str) -> dict | None:
    """
    Get basic info about a stock.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with stock info or None if not found
    """
    try:
        stock = yf.Ticker(ticker.upper().strip())
        info = stock.info
        return {
            "ticker": ticker.upper(),
            "name": info.get("shortName") or info.get("longName", ticker),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", ""),
            "current_price": info.get("regularMarketPrice") or info.get("previousClose"),
        }
    except Exception:
        return None
