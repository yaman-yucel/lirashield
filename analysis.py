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

from database import get_cpi_usd_rate_for_date, add_cpi_usd_rate, calculate_cumulative_cpi_daily


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

    1. First checks the database for stored rates (exact match if auto_fetch enabled)
    2. If auto_fetch=True and no exact match, attempts yfinance fetch and stores result
    3. If auto_fetch=False, falls back to closest earlier date in database

    Args:
        date_str: Date in YYYY-MM-DD format
        auto_fetch: Whether to auto-fetch from yfinance if not in database

    Returns:
        USD/TRY rate or None if unavailable
    """
    # When auto_fetch is enabled, only accept exact matches from DB
    # This prevents using stale rates from months ago
    db_rate = get_cpi_usd_rate_for_date(date_str, exact_match=auto_fetch)
    if db_rate is not None:
        return db_rate

    # Auto-fetch from yfinance if enabled and no exact match
    if auto_fetch:
        rate = fetch_usd_rate_from_yfinance(date_str)
        if rate is not None:
            # Store fetched rate for future use
            add_cpi_usd_rate(date_str, rate, source="yfinance_auto", notes="Auto-fetched")
            return rate

    # If auto_fetch is disabled, try fallback to closest earlier date
    if not auto_fetch:
        return get_cpi_usd_rate_for_date(date_str, exact_match=False)

    return None


def calculate_real_return(
    buy_price: float,
    current_price: float,
    buy_date: str,
    auto_fetch_usd: bool = False,
    tax_rate: float = 0,
) -> dict[str, float | str | None]:
    """
    Calculates Real Return using both USD and CPI as inflation benchmarks.

    Formula: ((After_Tax_Current / Buy_Price) / (1 + inflation)) - 1

    Tax is applied on TRY nominal gain:
        after_tax_current = current_price - (current_price - buy_price) * tax_rate

    If inflation is 20% and your stock rose 20%, your Real Gain is 0%.

    Args:
        buy_price: Purchase price per share in TRY
        current_price: Current price per share in TRY
        buy_date: Purchase date in YYYY-MM-DD format
        auto_fetch_usd: Whether to auto-fetch USD rates from yfinance
        tax_rate: Tax rate on TRY gains (0-100, e.g., 10 for 10%)

    Returns:
        Dictionary with nominal_pct, usd_inflation_pct, cpi_inflation_pct,
        real_return_usd_pct, real_return_cpi_pct (all after-tax)
        or error message if data is missing
    """
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Calculate after-tax current price (tax only applies to gains)
    try_gain = max(0, current_price - buy_price)  # Only tax gains, not losses
    tax_amount = try_gain * (tax_rate / 100)
    after_tax_current = current_price - tax_amount

    # Calculate nominal return (after tax)
    nominal_return = (after_tax_current - buy_price) / buy_price

    result: dict[str, float | str | None] = {
        "nominal_pct": round(nominal_return * 100, 2),
        "usd_inflation_pct": None,
        "real_return_usd_pct": None,
        "cpi_inflation_pct": None,
        "real_return_cpi_pct": None,
        "buy_usd": None,
        "current_usd": None,
        "tax_rate": tax_rate,
        "tax_amount_per_share": round(tax_amount, 4) if tax_rate > 0 else None,
    }

    # === USD-based calculation ===
    buy_usd = get_usd_rate(buy_date, auto_fetch=auto_fetch_usd)
    current_usd = get_usd_rate(current_date, auto_fetch=auto_fetch_usd)

    if buy_usd is not None and current_usd is not None:
        usd_change = (current_usd - buy_usd) / buy_usd
        real_return_usd = ((1 + nominal_return) / (1 + usd_change)) - 1

        result["usd_inflation_pct"] = round(usd_change * 100, 2)
        result["real_return_usd_pct"] = round(real_return_usd * 100, 2)
        result["buy_usd"] = round(buy_usd, 4)
        result["current_usd"] = round(current_usd, 4)

    # === CPI-based calculation ===
    # Use daily-compounded CPI for accurate partial month calculation
    cpi_change = calculate_cumulative_cpi_daily(buy_date, current_date)

    if cpi_change is not None:
        cpi_decimal = cpi_change / 100  # Convert percentage to decimal
        real_return_cpi = ((1 + nominal_return) / (1 + cpi_decimal)) - 1

        result["cpi_inflation_pct"] = round(cpi_change, 2)
        result["real_return_cpi_pct"] = round(real_return_cpi * 100, 2)

    # Check if we have at least one benchmark
    if result["real_return_usd_pct"] is None and result["real_return_cpi_pct"] is None:
        return {"error": f"Missing both USD and CPI data for {buy_date}. Add rates in USD/CPI tabs."}

    return result


def calculate_portfolio_summary(positions: list[dict], auto_fetch_usd: bool = False) -> dict[str, float]:
    """
    Calculate aggregate portfolio metrics.

    Args:
        positions: List of position dicts with buy_price, current_price, buy_date, quantity, tax_rate
        auto_fetch_usd: Whether to auto-fetch USD rates

    Returns:
        Summary with total_invested, current_value, nominal_gain, real_gain (USD & CPI)
    """
    total_invested = 0.0
    current_value = 0.0
    weighted_real_gains_usd: list[tuple[float, float]] = []
    weighted_real_gains_cpi: list[tuple[float, float]] = []

    for pos in positions:
        qty = pos.get("quantity", 1)
        buy_price = pos["buy_price"]
        current_price = pos["current_price"]
        tax_rate = pos.get("tax_rate", 0)

        invested = buy_price * qty
        current = current_price * qty

        total_invested += invested
        current_value += current

        result = calculate_real_return(buy_price, current_price, pos["buy_date"], auto_fetch_usd, tax_rate)
        if result.get("real_return_usd_pct") is not None:
            weighted_real_gains_usd.append((invested, result["real_return_usd_pct"]))
        if result.get("real_return_cpi_pct") is not None:
            weighted_real_gains_cpi.append((invested, result["real_return_cpi_pct"]))

    # Calculate weighted average real gains
    avg_real_gain_usd = 0.0
    if weighted_real_gains_usd and total_invested > 0:
        weighted_sum = sum(inv * gain for inv, gain in weighted_real_gains_usd)
        avg_real_gain_usd = weighted_sum / total_invested

    avg_real_gain_cpi = 0.0
    if weighted_real_gains_cpi and total_invested > 0:
        weighted_sum = sum(inv * gain for inv, gain in weighted_real_gains_cpi)
        avg_real_gain_cpi = weighted_sum / total_invested

    nominal_gain_pct = ((current_value - total_invested) / total_invested * 100) if total_invested > 0 else 0

    return {
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "nominal_gain_pct": round(nominal_gain_pct, 2),
        "avg_real_gain_usd_pct": round(avg_real_gain_usd, 2),
        "avg_real_gain_cpi_pct": round(avg_real_gain_cpi, 2),
    }
