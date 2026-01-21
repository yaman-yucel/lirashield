"""
Database module for portfolio and CPI/USD rate storage.
Uses SQLite for persistent storage of transactions and inflation benchmark data.

Supports multiple asset types:
- TEFAS: Turkish mutual funds (TRY denominated)
- USD_STOCK: US stocks (USD denominated)
- CASH: Cash holdings (TRY or USD)
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

import pandas as pd

DB_NAME = "portfolio.db"

# Asset type constants
ASSET_TEFAS = "TEFAS"
ASSET_USD_STOCK = "USD_STOCK"
ASSET_CASH = "CASH"

# Currency constants
CURRENCY_TRY = "TRY"
CURRENCY_USD = "USD"

# Transaction type constants
TX_BUY = "BUY"
TX_SELL = "SELL"


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Get a database connection with automatic commit/rollback and cleanup.

    Usage:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM table")
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initialize the database with transactions and CPI/USD rates tables."""
    with get_connection() as conn:
        c = conn.cursor()

        # Transactions table for portfolio tracking
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                quantity REAL NOT NULL,
                tax_rate REAL NOT NULL DEFAULT 0,
                asset_type TEXT NOT NULL DEFAULT 'TEFAS',
                currency TEXT NOT NULL DEFAULT 'TRY',
                transaction_type TEXT NOT NULL DEFAULT 'BUY',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migrations for existing databases
        c.execute("PRAGMA table_info(transactions)")
        columns = [col[1] for col in c.fetchall()]

        # Migration: Add tax_rate column if it doesn't exist
        if "tax_rate" not in columns:
            c.execute("ALTER TABLE transactions ADD COLUMN tax_rate REAL NOT NULL DEFAULT 0")

        # Migration: Add asset_type column if it doesn't exist
        if "asset_type" not in columns:
            c.execute("ALTER TABLE transactions ADD COLUMN asset_type TEXT NOT NULL DEFAULT 'TEFAS'")

        # Migration: Add currency column if it doesn't exist
        if "currency" not in columns:
            c.execute("ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'TRY'")

        # Migration: Add transaction_type column if it doesn't exist
        if "transaction_type" not in columns:
            c.execute("ALTER TABLE transactions ADD COLUMN transaction_type TEXT NOT NULL DEFAULT 'BUY'")

        # Migration: Add price_per_share column if it doesn't exist (nullable, for manual entry)
        if "price_per_share" not in columns:
            c.execute("ALTER TABLE transactions ADD COLUMN price_per_share REAL")

        # Migration: Drop price_per_share column if it exists (old migration - no longer needed)
        # This block is kept for historical reference but should not execute
        if False and "price_per_share" in columns:
            c.execute("""
                CREATE TABLE IF NOT EXISTS transactions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    tax_rate REAL NOT NULL DEFAULT 0,
                    asset_type TEXT NOT NULL DEFAULT 'TEFAS',
                    currency TEXT NOT NULL DEFAULT 'TRY',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("""
                INSERT INTO transactions_new (id, date, ticker, quantity, tax_rate, asset_type, currency, notes, created_at)
                SELECT id, date, ticker, quantity, COALESCE(tax_rate, 0), 'TEFAS', 'TRY', notes, created_at
                FROM transactions
            """)
            c.execute("DROP TABLE transactions")
            c.execute("ALTER TABLE transactions_new RENAME TO transactions")

        # USD/TRY rates table - for USD-based inflation proxy
        c.execute("""
            CREATE TABLE IF NOT EXISTS cpi_usd_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                usd_try_rate REAL NOT NULL,
                source TEXT DEFAULT 'manual',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Official CPI data table - from TCMB (Turkish Central Bank)
        c.execute("""
            CREATE TABLE IF NOT EXISTS cpi_official (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year_month TEXT NOT NULL UNIQUE,
                cpi_yoy REAL NOT NULL,
                cpi_mom REAL,
                source TEXT DEFAULT 'TCMB',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Fund prices table for TEFAS data and US stocks
        c.execute("""
            CREATE TABLE IF NOT EXISTS fund_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'TRY',
                source TEXT DEFAULT 'tefas',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, ticker)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_fund_prices_ticker ON fund_prices(ticker)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fund_prices_date ON fund_prices(date)")

        # Migration: Add currency column to fund_prices if it doesn't exist
        c.execute("PRAGMA table_info(fund_prices)")
        fp_columns = [col[1] for col in c.fetchall()]
        if "currency" not in fp_columns:
            c.execute("ALTER TABLE fund_prices ADD COLUMN currency TEXT NOT NULL DEFAULT 'TRY'")


# ============== TRANSACTION FUNCTIONS ==============


def add_transaction(
    date: str,
    ticker: str,
    quantity: float,
    tax_rate: float = 0,
    notes: str = "",
    asset_type: str = ASSET_TEFAS,
    currency: str = CURRENCY_TRY,
    transaction_type: str = TX_BUY,
    price_per_share: float | None = None,
) -> str:
    """
    Add a transaction (buy or sell) to the database.
    Price can be manually provided or looked up from fund_prices table.

    Args:
        date: Transaction date in YYYY-MM-DD format
        ticker: Stock/fund ticker symbol (or 'CASH' for cash holdings)
        quantity: Number of shares (or amount for cash) - always positive
        tax_rate: Tax rate on gains at sell (0-100, e.g., 10 for 10%)
        notes: Optional notes
        asset_type: TEFAS, USD_STOCK, or CASH
        currency: TRY or USD
        transaction_type: BUY or SELL
        price_per_share: Optional manual buy price. If None, price is looked up from fund_prices.
    """
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        ticker_upper = ticker.upper().strip()
        tx_type = transaction_type.upper() if transaction_type else TX_BUY

        if tx_type not in [TX_BUY, TX_SELL]:
            return f"❌ Invalid transaction type: {tx_type}. Must be BUY or SELL."

        # For cash, we don't need price lookup
        if asset_type == ASSET_CASH:
            with get_connection() as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO transactions (date, ticker, quantity, tax_rate, asset_type, currency, transaction_type, notes, price_per_share) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (valid_date, ticker_upper, float(quantity), float(tax_rate), asset_type, currency, tx_type, notes, 1.0),
                )
            action = "added" if tx_type == TX_BUY else "withdrawn"
            return f"✅ Cash {action}: {quantity:,.2f} {currency} on {valid_date}"

        # If price_per_share is provided, use it; otherwise look up from fund_prices
        if price_per_share is not None and price_per_share > 0:
            price = float(price_per_share)
        else:
            # Verify price exists in fund_prices (for validation)
            price = get_fund_price_for_date(ticker_upper, valid_date, exact_match=False)
            if price is None:
                source = "TEFAS" if asset_type == ASSET_TEFAS else "yfinance"
                return f"❌ No price found for {ticker_upper} on or before {valid_date}. Fetch {source} prices first or enter buy price manually."

        # For sells, verify we have enough shares
        if tx_type == TX_SELL:
            holdings = get_ticker_holdings(ticker_upper, valid_date)
            if holdings < quantity:
                return f"❌ Insufficient shares: you have {holdings:.4f} {ticker_upper} but trying to sell {quantity:.4f}"

        with get_connection() as conn:
            c = conn.cursor()
            # Only store price_per_share if it was manually provided
            stored_price = float(price_per_share) if price_per_share is not None and price_per_share > 0 else None
            c.execute(
                "INSERT INTO transactions (date, ticker, quantity, tax_rate, asset_type, currency, transaction_type, notes, price_per_share) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (valid_date, ticker_upper, float(quantity), float(tax_rate), asset_type, currency, tx_type, notes, stored_price),
            )

        action = "bought" if tx_type == TX_BUY else "sold"
        tax_str = f" (tax: {tax_rate}%)" if tax_rate > 0 else ""
        price_source = "manual" if price_per_share is not None else "auto"
        return f"✅ {tx_type}: {ticker_upper} x{quantity} @ {price:.6f} {currency} on {valid_date}{tax_str} ({price_source})"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def get_ticker_holdings(ticker: str, as_of_date: str | None = None) -> float:
    """
    Calculate the current holdings for a ticker using FIFO (buys - sells).

    Args:
        ticker: Stock/fund ticker symbol
        as_of_date: Optional date to calculate holdings as of (YYYY-MM-DD)

    Returns:
        Net quantity held (buys - sells)
    """
    with get_connection() as conn:
        c = conn.cursor()
        ticker_upper = ticker.upper().strip()

        if as_of_date:
            c.execute(
                """
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type = 'BUY' THEN quantity ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN transaction_type = 'SELL' THEN quantity ELSE 0 END), 0)
                FROM transactions 
                WHERE ticker = ? AND date <= ?
            """,
                (ticker_upper, as_of_date),
            )
        else:
            c.execute(
                """
                SELECT 
                    COALESCE(SUM(CASE WHEN transaction_type = 'BUY' OR transaction_type IS NULL THEN quantity ELSE 0 END), 0) -
                    COALESCE(SUM(CASE WHEN transaction_type = 'SELL' THEN quantity ELSE 0 END), 0)
                FROM transactions 
                WHERE ticker = ?
            """,
                (ticker_upper,),
            )

        result = c.fetchone()
        return float(result[0]) if result and result[0] else 0.0


def get_portfolio() -> pd.DataFrame:
    """Retrieve all transactions as a Pandas DataFrame with prices from stored price_per_share or fund_prices."""
    with get_connection() as conn:
        # Use stored price_per_share if available, otherwise look up from fund_prices
        # This handles weekends/holidays where exact date may not exist
        # For CASH assets, price_per_share is 1 (each unit is worth 1 of its currency)
        df = pd.read_sql_query(
            """
            SELECT 
                t.id,
                t.date,
                t.ticker,
                t.quantity,
                CASE 
                    WHEN t.asset_type = 'CASH' THEN 1.0
                    WHEN t.price_per_share IS NOT NULL THEN t.price_per_share
                    ELSE (SELECT fp.price FROM fund_prices fp 
                          WHERE fp.ticker = t.ticker AND fp.date <= t.date 
                          ORDER BY fp.date DESC LIMIT 1)
                END as price_per_share,
                t.tax_rate,
                t.asset_type,
                t.currency,
                COALESCE(t.transaction_type, 'BUY') as transaction_type,
                t.notes,
                t.created_at
            FROM transactions t
            ORDER BY t.date DESC
        """,
            conn,
        )
    return df


def get_portfolio_raw() -> pd.DataFrame:
    """Retrieve all transactions without price lookup (raw transaction data)."""
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
    return df


def get_unique_tickers() -> list[str]:
    """Get list of unique tickers from portfolio, sorted alphabetically."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT ticker FROM transactions ORDER BY ticker")
        tickers = [row[0] for row in c.fetchall()]
    return tickers


def get_unique_tickers_by_type(asset_type: str | None = None) -> list[str]:
    """Get list of unique tickers from portfolio, optionally filtered by asset type."""
    with get_connection() as conn:
        c = conn.cursor()
        if asset_type:
            c.execute("SELECT DISTINCT ticker FROM transactions WHERE asset_type = ? ORDER BY ticker", (asset_type,))
        else:
            c.execute("SELECT DISTINCT ticker FROM transactions ORDER BY ticker")
        tickers = [row[0] for row in c.fetchall()]
    return tickers


def get_tickers_with_info() -> list[dict]:
    """Get unique tickers with their asset type and currency info."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT ticker, asset_type, currency 
            FROM transactions 
            ORDER BY asset_type, ticker
        """)
        return [{"ticker": row[0], "asset_type": row[1], "currency": row[2]} for row in c.fetchall()]


def delete_transaction(transaction_id: int) -> str:
    """Delete a transaction by ID."""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            if c.rowcount > 0:
                return f"✅ Transaction #{transaction_id} deleted"
            return f"❌ Transaction #{transaction_id} not found"
    except Exception as e:
        return f"❌ Error: {e}"


# ============== CPI/USD RATE FUNCTIONS ==============


def add_cpi_usd_rate(date: str, rate: float, source: str = "manual", notes: str = "") -> str:
    """Add or update a CPI/USD rate for a specific date."""
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")

        with get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO cpi_usd_rates (date, usd_try_rate, source, notes) 
                   VALUES (?, ?, ?, ?)""",
                (valid_date, float(rate), source, notes),
            )
        return f"✅ USD/TRY rate for {valid_date}: {rate} ({source})"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def get_cpi_usd_rates() -> pd.DataFrame:
    """Retrieve all CPI/USD rates as a Pandas DataFrame."""
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM cpi_usd_rates ORDER BY date DESC", conn)
    return df


def get_cpi_usd_rate_for_date(date: str, exact_match: bool = False) -> float | None:
    """
    Get the USD/TRY rate for a specific date.

    Args:
        date: Date in YYYY-MM-DD format
        exact_match: If True, only return rate if exact date exists.
                     If False, fall back to closest earlier date.

    Returns:
        USD/TRY rate or None if not found
    """
    with get_connection() as conn:
        c = conn.cursor()

        # Try exact match first
        c.execute("SELECT usd_try_rate FROM cpi_usd_rates WHERE date = ?", (date,))
        result = c.fetchone()

        if result:
            return result[0]

        # If exact_match requested, don't fall back
        if exact_match:
            return None

        # If no exact match, find the closest earlier date
        c.execute("SELECT usd_try_rate FROM cpi_usd_rates WHERE date <= ? ORDER BY date DESC LIMIT 1", (date,))
        result = c.fetchone()

    return result[0] if result else None


def delete_cpi_usd_rate(rate_id: int) -> str:
    """Delete a CPI/USD rate by ID."""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM cpi_usd_rates WHERE id = ?", (rate_id,))
            if c.rowcount > 0:
                return f"✅ Rate #{rate_id} deleted"
            return f"❌ Rate #{rate_id} not found"
    except Exception as e:
        return f"❌ Error: {e}"


def bulk_import_cpi_usd_rates(csv_text: str) -> str:
    """
    Import multiple CPI/USD rates from CSV format.
    Expected format: date,rate (one per line)
    """
    try:
        lines = [line.strip() for line in csv_text.strip().split("\n") if line.strip()]
        imported = 0
        errors = []

        for line in lines:
            if "," not in line:
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                date_str = parts[0].strip()
                rate_str = parts[1].strip()
                try:
                    result = add_cpi_usd_rate(date_str, float(rate_str), source="bulk_import")
                    if result.startswith("✅"):
                        imported += 1
                    else:
                        errors.append(f"{date_str}: {result}")
                except ValueError:
                    errors.append(f"{date_str}: Invalid rate value")

        msg = f"✅ Imported {imported} rate(s)"
        if errors:
            msg += f"\n⚠️ Errors: {len(errors)}\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more errors"
        return msg
    except Exception as e:
        return f"❌ Import error: {e}"


# ============== OFFICIAL CPI FUNCTIONS (TCMB) ==============


def add_cpi_official(year_month: str, cpi_yoy: float, cpi_mom: float | None = None, notes: str = "") -> str:
    """
    Add or update official CPI data for a specific month.

    Args:
        year_month: Format YYYY-MM (e.g., "2024-12")
        cpi_yoy: Year-over-Year inflation rate (e.g., 44.38 for 44.38%)
        cpi_mom: Month-over-Month inflation rate (e.g., 1.03 for 1.03%)
    """
    try:
        parts = year_month.split("-")
        if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
            return "❌ Error: Format must be YYYY-MM (e.g., 2024-12)"

        with get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO cpi_official (year_month, cpi_yoy, cpi_mom, source, notes) 
                   VALUES (?, ?, ?, 'TCMB', ?)""",
                (year_month, float(cpi_yoy), float(cpi_mom) if cpi_mom is not None else None, notes),
            )
        return f"✅ CPI for {year_month}: YoY={cpi_yoy}%, MoM={cpi_mom}%"
    except Exception as e:
        return f"❌ Error: {e}"


def get_cpi_official_data() -> pd.DataFrame:
    """Retrieve all official CPI data as a Pandas DataFrame."""
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM cpi_official ORDER BY year_month DESC", conn)
    return df


def delete_cpi_official(cpi_id: int) -> str:
    """Delete a CPI entry by ID."""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM cpi_official WHERE id = ?", (cpi_id,))
            if c.rowcount > 0:
                return f"✅ CPI entry #{cpi_id} deleted"
            return f"❌ CPI entry #{cpi_id} not found"
    except Exception as e:
        return f"❌ Error: {e}"


def bulk_import_cpi_official(csv_text: str) -> str:
    """
    Import multiple CPI entries from CSV format.
    Expected format: year_month,cpi_yoy,cpi_mom (one per line)
    Supports both MM-YYYY and YYYY-MM formats.
    """
    try:
        lines = [line.strip() for line in csv_text.strip().split("\n") if line.strip()]
        imported = 0
        errors = []

        for line in lines:
            if "," not in line:
                continue
            parts = line.split(",")
            if len(parts) >= 2:
                ym_str = parts[0].strip()
                yoy_str = parts[1].strip()
                mom_str = parts[2].strip() if len(parts) >= 3 else None

                # Convert MM-YYYY to YYYY-MM if needed
                if "-" in ym_str:
                    ym_parts = ym_str.split("-")
                    if len(ym_parts[0]) == 2 and len(ym_parts[1]) == 4:
                        ym_str = f"{ym_parts[1]}-{ym_parts[0]}"

                try:
                    mom_val = float(mom_str) if mom_str else None
                    result = add_cpi_official(ym_str, float(yoy_str), mom_val)
                    if result.startswith("✅"):
                        imported += 1
                    else:
                        errors.append(f"{ym_str}: {result}")
                except ValueError:
                    errors.append(f"{ym_str}: Invalid value")

        msg = f"✅ Imported {imported} CPI record(s)"
        if errors:
            msg += f"\n⚠️ Errors: {len(errors)}\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more errors"
        return msg
    except Exception as e:
        return f"❌ Import error: {e}"


def calculate_cumulative_cpi(start_year_month: str, end_year_month: str) -> float | None:
    """
    Calculate cumulative inflation between two months using MoM rates.
    Returns the total percentage change (e.g., 25.5 for 25.5% inflation).

    Note: This is the simple month-to-month version. For date-accurate calculation,
    use calculate_cumulative_cpi_daily() instead.
    """
    with get_connection() as conn:
        c = conn.cursor()

        c.execute(
            """SELECT year_month, cpi_mom FROM cpi_official 
               WHERE year_month > ? AND year_month <= ? 
               ORDER BY year_month""",
            (start_year_month, end_year_month),
        )
        rows = c.fetchall()

    if not rows:
        return None

    if any(row[1] is None for row in rows):
        return None

    # Compound the monthly rates
    cumulative = 1.0
    for _, mom in rows:
        cumulative *= 1 + (mom / 100)

    return (cumulative - 1) * 100


def get_days_in_month(year: int, month: int) -> int:
    """Return the number of days in a given month."""
    import calendar

    return calendar.monthrange(year, month)[1]


def calculate_cumulative_cpi_daily(start_date: str, end_date: str) -> float | None:
    """
    Calculate cumulative inflation between two dates using daily-compounded CPI.

    Uses monthly CPI data but interpolates daily using compounding:
    - daily_rate = (1 + monthly_rate)^(1/days_in_month) - 1

    For partial months:
    - Start month: Calculate from buy_day to end of month
    - End month: Calculate from start of month to today
    - Full months in between: Use full monthly rate

    Args:
        start_date: Purchase date in YYYY-MM-DD format
        end_date: Current date in YYYY-MM-DD format

    Returns:
        Cumulative inflation as percentage (e.g., 25.5 for 25.5%), or None if data missing
    """
    from datetime import datetime

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    start_year, start_month, start_day = start_dt.year, start_dt.month, start_dt.day
    end_year, end_month, end_day = end_dt.year, end_dt.month, end_dt.day

    start_ym = f"{start_year:04d}-{start_month:02d}"
    end_ym = f"{end_year:04d}-{end_month:02d}"

    # If same month, calculate partial month only
    # Days held = transitions from start_day to end_day = end_day - start_day
    if start_ym == end_ym:
        days_held = end_day - start_day
        if days_held <= 0:
            return 0.0
        mom = get_cpi_mom_for_month(start_ym)
        if mom is None:
            return None
        days_in_month = get_days_in_month(start_year, start_month)
        # Daily compounding: partial = (1 + mom)^(days_held/days_in_month) - 1
        partial = (1 + mom / 100) ** (days_held / days_in_month) - 1
        return partial * 100

    cumulative = 1.0

    # === Start month (partial): from buy_day to end of month ===
    start_mom = get_cpi_mom_for_month(start_ym)
    if start_mom is None:
        return None

    days_in_start_month = get_days_in_month(start_year, start_month)
    days_remaining_start = days_in_start_month - start_day + 1  # Include buy day

    # Daily compounding for partial start month
    start_partial = (1 + start_mom / 100) ** (days_remaining_start / days_in_start_month)
    cumulative *= start_partial

    # === Full months in between ===
    with get_connection() as conn:
        c = conn.cursor()

        # Get months strictly between start and end
        c.execute(
            """SELECT year_month, cpi_mom FROM cpi_official 
               WHERE year_month > ? AND year_month < ? 
               ORDER BY year_month""",
            (start_ym, end_ym),
        )
        rows = c.fetchall()

    # Check for missing MoM data in full months
    if any(row[1] is None for row in rows):
        return None

    for _, mom in rows:
        cumulative *= 1 + (mom / 100)

    # === End month (partial): from start of month to today ===
    # On day 1, you've experienced 0 days of that month's inflation
    # On day 21, you've experienced 20 days (day 1→2, 2→3, ..., 20→21)
    days_elapsed_end = end_day - 1

    if days_elapsed_end > 0:
        end_mom = get_cpi_mom_for_month(end_ym)

        # If end month CPI not available, use the latest available month's rate
        if end_mom is None:
            latest = get_latest_cpi_mom()
            if latest is not None:
                end_mom = latest[1]

        if end_mom is not None:
            days_in_end_month = get_days_in_month(end_year, end_month)

            # Daily compounding for partial end month
            end_partial = (1 + end_mom / 100) ** (days_elapsed_end / days_in_end_month)
            cumulative *= end_partial

    return (cumulative - 1) * 100


def get_cpi_mom_for_month(year_month: str) -> float | None:
    """Get the MoM CPI rate for a specific month. Returns None if not found."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT cpi_mom FROM cpi_official WHERE year_month = ?", (year_month,))
        result = c.fetchone()
    return result[0] if result and result[0] is not None else None


def get_latest_cpi_mom() -> tuple[str, float] | None:
    """Get the most recent CPI MoM rate available. Returns (year_month, mom_rate) or None."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT year_month, cpi_mom FROM cpi_official WHERE cpi_mom IS NOT NULL ORDER BY year_month DESC LIMIT 1")
        result = c.fetchone()
    return (result[0], result[1]) if result else None


# ============== FUND PRICES TABLE (TEFAS) ==============


def add_fund_price(date: str, ticker: str, price: float, source: str = "tefas", currency: str = CURRENCY_TRY) -> str:
    """
    Add a fund price entry. Uses INSERT OR IGNORE to skip existing dates.

    Args:
        date: Date in YYYY-MM-DD format
        ticker: Fund ticker symbol
        price: Fund price
        source: Data source (default: tefas)
        currency: Currency of the price (TRY or USD)

    Returns:
        Status message
    """
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        with get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """INSERT OR IGNORE INTO fund_prices (date, ticker, price, currency, source) 
                   VALUES (?, ?, ?, ?, ?)""",
                (valid_date, ticker.upper().strip(), float(price), currency, source),
            )
            inserted = c.rowcount > 0
        if inserted:
            return f"✅ Price added: {ticker.upper()} @ {price:.6f} {currency} on {valid_date}"
        return f"⏭️ Price already exists: {ticker.upper()} on {valid_date}"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def bulk_add_fund_prices(prices: list[tuple[str, str, float]], source: str = "tefas", currency: str = CURRENCY_TRY) -> tuple[int, int]:
    """
    Bulk insert fund prices. Skips existing dates (no updates).

    Args:
        prices: List of (date, ticker, price) tuples
        source: Data source
        currency: Currency of the prices (TRY or USD)

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    with get_connection() as conn:
        c = conn.cursor()
        inserted = 0
        skipped = 0

        for date, ticker, price in prices:
            try:
                c.execute(
                    """INSERT OR IGNORE INTO fund_prices (date, ticker, price, currency, source) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (date, ticker.upper().strip(), float(price), currency, source),
                )
                if c.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

    return inserted, skipped


def get_fund_prices(ticker: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    """
    Get fund prices for a ticker, optionally filtered by date range.

    Args:
        ticker: Fund ticker symbol
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)

    Returns:
        DataFrame with date, ticker, price columns
    """
    with get_connection() as conn:
        query = "SELECT date, ticker, price FROM fund_prices WHERE ticker = ?"
        params: list = [ticker.upper().strip()]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"
        df = pd.read_sql_query(query, conn, params=params)
    return df


def get_latest_fund_price(ticker: str) -> tuple[str, float, str] | None:
    """
    Get the most recent price for a fund.

    Returns:
        Tuple of (date, price, currency) or None if not found
    """
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT date, price, COALESCE(currency, 'TRY') FROM fund_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1",
            (ticker.upper().strip(),),
        )
        result = c.fetchone()
    return (result[0], result[1], result[2]) if result else None


def get_fund_price_for_date(ticker: str, date: str, exact_match: bool = False) -> float | None:
    """
    Get fund price for a specific date.

    Args:
        ticker: Fund ticker symbol
        date: Date in YYYY-MM-DD format
        exact_match: If True, only return price if exact date exists.
                     If False, fall back to closest earlier date.

    Returns:
        Price or None if not found
    """
    with get_connection() as conn:
        c = conn.cursor()

        # Try exact match first
        c.execute(
            "SELECT price FROM fund_prices WHERE ticker = ? AND date = ?",
            (ticker.upper().strip(), date),
        )
        result = c.fetchone()

        if result:
            return result[0]

        if exact_match:
            return None

        # Fall back to closest earlier date
        c.execute(
            "SELECT price FROM fund_prices WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (ticker.upper().strip(), date),
        )
        result = c.fetchone()
    return result[0] if result else None


def get_oldest_fund_price_date(ticker: str) -> str | None:
    """Get the oldest price date for a fund."""
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT MIN(date) FROM fund_prices WHERE ticker = ?",
            (ticker.upper().strip(),),
        )
        result = c.fetchone()
    return result[0] if result and result[0] else None


def get_fund_price_date_range(ticker: str) -> tuple[str, str] | None:
    """
    Get the date range of stored prices for a fund.

    Returns:
        Tuple of (oldest_date, newest_date) or None if no prices
    """
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT MIN(date), MAX(date) FROM fund_prices WHERE ticker = ?",
            (ticker.upper().strip(),),
        )
        result = c.fetchone()
    if result and result[0] and result[1]:
        return (result[0], result[1])
    return None


def get_all_fund_latest_prices() -> dict[str, tuple[str, float, str]]:
    """
    Get the latest price for all funds in the database.

    Returns:
        Dict mapping ticker -> (date, price, currency)
    """
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT ticker, date, price, COALESCE(currency, 'TRY') as currency FROM fund_prices fp1
            WHERE date = (SELECT MAX(date) FROM fund_prices fp2 WHERE fp2.ticker = fp1.ticker)
        """)
        results = c.fetchall()
    return {row[0]: (row[1], row[2], row[3]) for row in results}
