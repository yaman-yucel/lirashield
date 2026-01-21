"""
Analysis module for calculating Real Returns adjusted for inflation.

Supports two inflation benchmarks:
1. USD/TRY exchange rate (street method)
2. Official CPI data from TCMB (Turkish Central Bank)

Uses stored rates from the database as the primary source.
Falls back to yfinance for automatic USD fetching when manual data is unavailable.
"""

from datetime import datetime, timedelta

import yfinance as yf

from database import get_cpi_usd_rate_for_date, add_cpi_usd_rate


def fetch_usd_rate_from_yfinance(date_str: str) -> float | None:
    """
    Fetches the USD/TRY close price for a specific date using yfinance.
    Returns None if data cannot be fetched.
    """
    try:
        start_date = datetime.strptime(date_str, "%Y-%m-%d")
        end_date = start_date + timedelta(days=5)  # Window to handle weekends/holidays

        ticker = "TRY=X"  # USD/TRY exchange rate
        data = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)

        if not data.empty:
            # Handle both single and multi-index columns
            if "Close" in data.columns:
                return float(data["Close"].iloc[0])
            elif ("Close", "TRY=X") in data.columns:
                return float(data[("Close", "TRY=X")].iloc[0])
        return None
    except Exception:
        return None


def get_usd_rate(date_str: str, auto_fetch: bool = False) -> float | None:
    """
    Get USD/TRY rate for a date.

    1. First checks the database for stored rates
    2. If auto_fetch=True and no data found, attempts yfinance fetch and stores result

    Args:
        date_str: Date in YYYY-MM-DD format
        auto_fetch: Whether to auto-fetch from yfinance if not in database

    Returns:
        USD/TRY rate or None if unavailable
    """
    # Try database first
    db_rate = get_cpi_usd_rate_for_date(date_str)
    if db_rate is not None:
        return db_rate

    # Auto-fetch from yfinance if enabled
    if auto_fetch:
        rate = fetch_usd_rate_from_yfinance(date_str)
        if rate is not None:
            # Store fetched rate for future use
            add_cpi_usd_rate(date_str, rate, source="yfinance_auto", notes="Auto-fetched")
            return rate

    return None


def calculate_real_return(buy_price: float, current_price: float, buy_date: str, auto_fetch_usd: bool = False) -> dict[str, float | str]:
    """
    Calculates Real Return using USD as the inflation proxy.

    Formula: ((Current_Price / Buy_Price) / (Current_USD / Buy_USD)) - 1

    If the USD rose 20% and your stock rose 20%, your Real Gain is 0%.

    Args:
        buy_price: Purchase price per share in TRY
        current_price: Current price per share in TRY
        buy_date: Purchase date in YYYY-MM-DD format
        auto_fetch_usd: Whether to auto-fetch USD rates from yfinance

    Returns:
        Dictionary with nominal_pct, usd_inflation_pct, real_return_pct
        or error message if USD data is missing
    """
    # Get buy date USD rate
    buy_usd = get_usd_rate(buy_date, auto_fetch=auto_fetch_usd)

    # Get current USD rate (today)
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_usd = get_usd_rate(current_date, auto_fetch=auto_fetch_usd)

    # Return error if USD data is missing
    if buy_usd is None:
        return {"error": f"Missing USD rate for {buy_date}. Add it in CPI/USD tab."}
    if current_usd is None:
        return {"error": f"Missing USD rate for today ({current_date}). Add it in CPI/USD tab."}

    # Calculate returns
    nominal_return = (current_price - buy_price) / buy_price
    usd_change = (current_usd - buy_usd) / buy_usd

    # Real Return Formula: ((1 + nominal) / (1 + inflation)) - 1
    real_return = ((1 + nominal_return) / (1 + usd_change)) - 1

    return {
        "nominal_pct": round(nominal_return * 100, 2),
        "usd_inflation_pct": round(usd_change * 100, 2),
        "real_return_pct": round(real_return * 100, 2),
        "buy_usd": round(buy_usd, 4),
        "current_usd": round(current_usd, 4),
    }


def calculate_portfolio_summary(positions: list[dict], auto_fetch_usd: bool = False) -> dict[str, float]:
    """
    Calculate aggregate portfolio metrics.

    Args:
        positions: List of position dicts with buy_price, current_price, buy_date, quantity
        auto_fetch_usd: Whether to auto-fetch USD rates

    Returns:
        Summary with total_invested, current_value, nominal_gain, real_gain
    """
    total_invested = 0.0
    current_value = 0.0
    weighted_real_gains = []

    for pos in positions:
        qty = pos.get("quantity", 1)
        buy_price = pos["buy_price"]
        current_price = pos["current_price"]

        invested = buy_price * qty
        current = current_price * qty

        total_invested += invested
        current_value += current

        result = calculate_real_return(buy_price, current_price, pos["buy_date"], auto_fetch_usd)
        if "real_return_pct" in result:
            weighted_real_gains.append((invested, result["real_return_pct"]))

    # Calculate weighted average real gain
    if weighted_real_gains and total_invested > 0:
        weighted_sum = sum(inv * gain for inv, gain in weighted_real_gains)
        avg_real_gain = weighted_sum / total_invested
    else:
        avg_real_gain = 0.0

    nominal_gain_pct = ((current_value - total_invested) / total_invested * 100) if total_invested > 0 else 0

    return {
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "nominal_gain_pct": round(nominal_gain_pct, 2),
        "avg_real_gain_pct": round(avg_real_gain, 2),
    }
