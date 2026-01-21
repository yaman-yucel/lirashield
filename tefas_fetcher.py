"""
TEFAS price fetching module.

Fetches historical fund prices from TEFAS (Turkey Electronic Fund Trading Platform)
and stores them in the database. Uses INSERT OR IGNORE to avoid updating existing records.
"""

from datetime import datetime, timedelta

from tefas import Crawler

from database import (
    bulk_add_fund_prices,
    get_fund_price_date_range,
    get_oldest_fund_price_date,
    get_latest_fund_price,
)


CHUNK_DAYS = 60  # TEFAS API has ~90 day limit, use 60 for safety


def fetch_fund_prices(
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
    years_back: int = 5,
) -> tuple[int, int, str]:
    """
    Fetch fund prices from TEFAS and store in database.
    Only inserts new records, does not update existing ones.

    Uses chunked requests (60 days at a time) due to TEFAS API limits.

    Args:
        ticker: Fund ticker code (e.g., 'MAC', 'TI2')
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
        crawler = Crawler()

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        total_inserted = 0
        total_skipped = 0
        all_prices = []

        # Fetch in chunks to avoid API limits
        current_start = start_dt
        while current_start < end_dt:
            current_end = min(current_start + timedelta(days=CHUNK_DAYS), end_dt)

            chunk_start = current_start.strftime("%Y-%m-%d")
            chunk_end = current_end.strftime("%Y-%m-%d")

            try:
                data = crawler.fetch(start=chunk_start, end=chunk_end, name=ticker)

                if not data.empty:
                    for _, row in data.iterrows():
                        date_str = row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"])
                        all_prices.append((date_str, ticker, float(row["price"])))
            except Exception:
                pass  # Skip failed chunks, continue with others

            current_start = current_end + timedelta(days=1)

        if not all_prices:
            return 0, 0, f"⚠️ No data found for {ticker} between {start_date} and {end_date}"

        # Bulk insert all collected prices
        inserted, skipped = bulk_add_fund_prices(all_prices, source="tefas")

        return inserted, skipped, f"✅ {ticker}: {inserted} new prices added, {skipped} already existed"

    except Exception as e:
        return 0, 0, f"❌ Error fetching {ticker}: {e}"


def update_fund_prices(ticker: str) -> tuple[int, int, str]:
    """
    Update prices for a fund - only fetches missing recent data.
    Checks the latest stored date and fetches from there to today.

    Args:
        ticker: Fund ticker code

    Returns:
        Tuple of (inserted_count, skipped_count, status_message)
    """
    ticker = ticker.upper().strip()
    today = datetime.now().strftime("%Y-%m-%d")

    latest = get_latest_fund_price(ticker)

    if latest is None:
        # No data exists, fetch full history
        return fetch_fund_prices(ticker, end_date=today)

    latest_date, _ = latest

    # Check if we're already up to date (within last 3 days to account for weekends/holidays)
    days_since_latest = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
    if days_since_latest <= 3:
        return 0, 0, f"✅ {ticker} is up to date (latest: {latest_date})"

    # Fetch from day after latest to today
    start_dt = datetime.strptime(latest_date, "%Y-%m-%d") + timedelta(days=1)
    start_date = start_dt.strftime("%Y-%m-%d")

    inserted, skipped, msg = fetch_fund_prices(ticker, start_date=start_date, end_date=today)

    # If no new data found but we have existing data, consider it up to date
    # (could be weekend/holiday or market hasn't closed yet)
    if inserted == 0 and skipped == 0 and "No data found" in msg:
        return 0, 0, f"✅ {ticker} is up to date (latest: {latest_date})"

    return inserted, skipped, msg


def fetch_prices_for_new_ticker(ticker: str, transaction_date: str) -> tuple[int, int, str]:
    """
    Fetch historical prices for a newly added ticker.
    Fetches from 5 years before the transaction date (or fund inception) to today.

    Args:
        ticker: Fund ticker code
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
            return update_fund_prices(ticker)
        else:
            # Need to fetch older data before the transaction
            # Fetch from 1 year before transaction to oldest existing
            start_dt = datetime.strptime(transaction_date, "%Y-%m-%d") - timedelta(days=365)
            start_date = start_dt.strftime("%Y-%m-%d")
            return fetch_fund_prices(ticker, start_date=start_date, end_date=oldest)

    # No existing data - fetch from 5 years back to today
    tx_dt = datetime.strptime(transaction_date, "%Y-%m-%d")
    start_dt = tx_dt - timedelta(days=365 * 5)
    start_date = start_dt.strftime("%Y-%m-%d")

    return fetch_fund_prices(ticker, start_date=start_date, end_date=today)


def get_current_price(ticker: str) -> float | None:
    """
    Get the most recent price for a fund.
    First tries the database, then fetches from TEFAS if not recent enough.

    Args:
        ticker: Fund ticker code

    Returns:
        Current price or None if not available
    """
    ticker = ticker.upper().strip()
    today = datetime.now().strftime("%Y-%m-%d")

    latest = get_latest_fund_price(ticker)

    if latest:
        latest_date, price = latest
        # If data is from today or yesterday (markets might be closed), return it
        days_old = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
        if days_old <= 3:  # Allow weekend gap
            return price

    # Try to fetch fresh data
    inserted, _, _ = update_fund_prices(ticker)

    # Get the updated latest price
    latest = get_latest_fund_price(ticker)
    return latest[1] if latest else None


def is_valid_tefas_fund(ticker: str) -> bool:
    """
    Check if a ticker is a valid TEFAS fund by attempting to fetch recent data.

    Args:
        ticker: Fund ticker code to validate

    Returns:
        True if valid TEFAS fund, False otherwise
    """
    try:
        crawler = Crawler()
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        data = crawler.fetch(start=week_ago, end=today, name=ticker.upper().strip())
        return not data.empty
    except Exception:
        return False
