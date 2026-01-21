"""
Database module for portfolio and CPI/USD rate storage.
Uses SQLite for persistent storage of transactions and inflation benchmark data.
"""

import sqlite3
from datetime import datetime

import pandas as pd

DB_NAME = "portfolio.db"


def get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    return sqlite3.connect(DB_NAME)


def init_db() -> None:
    """Initialize the database with transactions and CPI/USD rates tables."""
    conn = get_connection()
    c = conn.cursor()

    # Transactions table for portfolio tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            tax_rate REAL NOT NULL DEFAULT 0,
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

    # Migration: Drop price_per_share column if it exists
    # SQLite doesn't support DROP COLUMN in older versions, so we recreate the table
    if "price_per_share" in columns:
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                quantity REAL NOT NULL,
                tax_rate REAL NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            INSERT INTO transactions_new (id, date, ticker, quantity, tax_rate, notes, created_at)
            SELECT id, date, ticker, quantity, COALESCE(tax_rate, 0), notes, created_at
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

    # Fund prices table for TEFAS data
    c.execute("""
        CREATE TABLE IF NOT EXISTS fund_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            price REAL NOT NULL,
            source TEXT DEFAULT 'tefas',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, ticker)
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_fund_prices_ticker ON fund_prices(ticker)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_fund_prices_date ON fund_prices(date)")

    conn.commit()
    conn.close()


# ============== TRANSACTION FUNCTIONS ==============


def add_transaction(date: str, ticker: str, quantity: float, tax_rate: float = 0, notes: str = "") -> str:
    """
    Add a buy transaction to the database.
    Price is looked up from fund_prices table when retrieving portfolio.

    Args:
        date: Purchase date in YYYY-MM-DD format
        ticker: Stock/fund ticker symbol
        quantity: Number of shares
        tax_rate: Tax rate on TRY gains at sell (0-100, e.g., 10 for 10%)
        notes: Optional notes
    """
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        ticker_upper = ticker.upper().strip()

        # Verify price exists in fund_prices (for validation)
        price = get_fund_price_for_date(ticker_upper, valid_date, exact_match=False)
        if price is None:
            return f"❌ No price found for {ticker_upper} on or before {valid_date}. Fetch TEFAS prices first."

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO transactions (date, ticker, quantity, tax_rate, notes) VALUES (?, ?, ?, ?, ?)",
            (valid_date, ticker_upper, float(quantity), float(tax_rate), notes),
        )
        conn.commit()
        conn.close()
        tax_str = f" (tax: {tax_rate}%)" if tax_rate > 0 else ""
        return f"✅ Transaction added: {ticker_upper} x{quantity} @ {price:.6f} TRY on {valid_date}{tax_str}"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def get_portfolio() -> pd.DataFrame:
    """Retrieve all transactions as a Pandas DataFrame with buy prices from fund_prices."""
    conn = get_connection()
    # Get price from fund_prices using subquery with fallback to closest earlier date
    # This handles weekends/holidays where exact date may not exist
    df = pd.read_sql_query(
        """
        SELECT 
            t.id,
            t.date,
            t.ticker,
            t.quantity,
            (SELECT fp.price FROM fund_prices fp 
             WHERE fp.ticker = t.ticker AND fp.date <= t.date 
             ORDER BY fp.date DESC LIMIT 1) as price_per_share,
            t.tax_rate,
            t.notes,
            t.created_at
        FROM transactions t
        ORDER BY t.date DESC
    """,
        conn,
    )
    conn.close()
    return df


def get_portfolio_raw() -> pd.DataFrame:
    """Retrieve all transactions without price lookup (raw transaction data)."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
    conn.close()
    return df


def get_unique_tickers() -> list[str]:
    """Get list of unique tickers from portfolio, sorted alphabetically."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT ticker FROM transactions ORDER BY ticker")
    tickers = [row[0] for row in c.fetchall()]
    conn.close()
    return tickers


def delete_transaction(transaction_id: int) -> str:
    """Delete a transaction by ID."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        if c.rowcount > 0:
            conn.commit()
            conn.close()
            return f"✅ Transaction #{transaction_id} deleted"
        conn.close()
        return f"❌ Transaction #{transaction_id} not found"
    except Exception as e:
        return f"❌ Error: {e}"


# ============== CPI/USD RATE FUNCTIONS ==============


def add_cpi_usd_rate(date: str, rate: float, source: str = "manual", notes: str = "") -> str:
    """Add or update a CPI/USD rate for a specific date."""
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO cpi_usd_rates (date, usd_try_rate, source, notes) 
               VALUES (?, ?, ?, ?)""",
            (valid_date, float(rate), source, notes),
        )
        conn.commit()
        conn.close()
        return f"✅ USD/TRY rate for {valid_date}: {rate} ({source})"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def get_cpi_usd_rates() -> pd.DataFrame:
    """Retrieve all CPI/USD rates as a Pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM cpi_usd_rates ORDER BY date DESC", conn)
    conn.close()
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
    conn = get_connection()
    c = conn.cursor()

    # Try exact match first
    c.execute("SELECT usd_try_rate FROM cpi_usd_rates WHERE date = ?", (date,))
    result = c.fetchone()

    if result:
        conn.close()
        return result[0]

    # If exact_match requested, don't fall back
    if exact_match:
        conn.close()
        return None

    # If no exact match, find the closest earlier date
    c.execute("SELECT usd_try_rate FROM cpi_usd_rates WHERE date <= ? ORDER BY date DESC LIMIT 1", (date,))
    result = c.fetchone()
    conn.close()

    return result[0] if result else None


def delete_cpi_usd_rate(rate_id: int) -> str:
    """Delete a CPI/USD rate by ID."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM cpi_usd_rates WHERE id = ?", (rate_id,))
        if c.rowcount > 0:
            conn.commit()
            conn.close()
            return f"✅ Rate #{rate_id} deleted"
        conn.close()
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

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO cpi_official (year_month, cpi_yoy, cpi_mom, source, notes) 
               VALUES (?, ?, ?, 'TCMB', ?)""",
            (year_month, float(cpi_yoy), float(cpi_mom) if cpi_mom is not None else None, notes),
        )
        conn.commit()
        conn.close()
        return f"✅ CPI for {year_month}: YoY={cpi_yoy}%, MoM={cpi_mom}%"
    except Exception as e:
        return f"❌ Error: {e}"


def get_cpi_official_data() -> pd.DataFrame:
    """Retrieve all official CPI data as a Pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM cpi_official ORDER BY year_month DESC", conn)
    conn.close()
    return df


def delete_cpi_official(cpi_id: int) -> str:
    """Delete a CPI entry by ID."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM cpi_official WHERE id = ?", (cpi_id,))
        if c.rowcount > 0:
            conn.commit()
            conn.close()
            return f"✅ CPI entry #{cpi_id} deleted"
        conn.close()
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
    conn = get_connection()
    c = conn.cursor()

    c.execute(
        """SELECT year_month, cpi_mom FROM cpi_official 
           WHERE year_month > ? AND year_month <= ? 
           ORDER BY year_month""",
        (start_year_month, end_year_month),
    )
    rows = c.fetchall()
    conn.close()

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
    conn = get_connection()
    c = conn.cursor()

    # Get months strictly between start and end
    c.execute(
        """SELECT year_month, cpi_mom FROM cpi_official 
           WHERE year_month > ? AND year_month < ? 
           ORDER BY year_month""",
        (start_ym, end_ym),
    )
    rows = c.fetchall()
    conn.close()

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
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT cpi_mom FROM cpi_official WHERE year_month = ?", (year_month,))
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] is not None else None


def get_latest_cpi_mom() -> tuple[str, float] | None:
    """Get the most recent CPI MoM rate available. Returns (year_month, mom_rate) or None."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT year_month, cpi_mom FROM cpi_official WHERE cpi_mom IS NOT NULL ORDER BY year_month DESC LIMIT 1")
    result = c.fetchone()
    conn.close()
    return (result[0], result[1]) if result else None


# ============== FUND PRICES TABLE (TEFAS) ==============


def add_fund_price(date: str, ticker: str, price: float, source: str = "tefas") -> str:
    """
    Add a fund price entry. Uses INSERT OR IGNORE to skip existing dates.

    Args:
        date: Date in YYYY-MM-DD format
        ticker: Fund ticker symbol
        price: Fund price in TRY
        source: Data source (default: tefas)

    Returns:
        Status message
    """
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
        conn = get_connection()
        c = conn.cursor()
        c.execute(
            """INSERT OR IGNORE INTO fund_prices (date, ticker, price, source) 
               VALUES (?, ?, ?, ?)""",
            (valid_date, ticker.upper().strip(), float(price), source),
        )
        inserted = c.rowcount > 0
        conn.commit()
        conn.close()
        if inserted:
            return f"✅ Price added: {ticker.upper()} @ {price:.6f} on {valid_date}"
        return f"⏭️ Price already exists: {ticker.upper()} on {valid_date}"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def bulk_add_fund_prices(prices: list[tuple[str, str, float]], source: str = "tefas") -> tuple[int, int]:
    """
    Bulk insert fund prices. Skips existing dates (no updates).

    Args:
        prices: List of (date, ticker, price) tuples
        source: Data source

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    conn = get_connection()
    c = conn.cursor()
    inserted = 0
    skipped = 0

    for date, ticker, price in prices:
        try:
            c.execute(
                """INSERT OR IGNORE INTO fund_prices (date, ticker, price, source) 
                   VALUES (?, ?, ?, ?)""",
                (date, ticker.upper().strip(), float(price), source),
            )
            if c.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()
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
    conn = get_connection()
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
    conn.close()
    return df


def get_latest_fund_price(ticker: str) -> tuple[str, float] | None:
    """
    Get the most recent price for a fund.

    Returns:
        Tuple of (date, price) or None if not found
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT date, price FROM fund_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1",
        (ticker.upper().strip(),),
    )
    result = c.fetchone()
    conn.close()
    return (result[0], result[1]) if result else None


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
    conn = get_connection()
    c = conn.cursor()

    # Try exact match first
    c.execute(
        "SELECT price FROM fund_prices WHERE ticker = ? AND date = ?",
        (ticker.upper().strip(), date),
    )
    result = c.fetchone()

    if result:
        conn.close()
        return result[0]

    if exact_match:
        conn.close()
        return None

    # Fall back to closest earlier date
    c.execute(
        "SELECT price FROM fund_prices WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 1",
        (ticker.upper().strip(), date),
    )
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def get_oldest_fund_price_date(ticker: str) -> str | None:
    """Get the oldest price date for a fund."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT MIN(date) FROM fund_prices WHERE ticker = ?",
        (ticker.upper().strip(),),
    )
    result = c.fetchone()
    conn.close()
    return result[0] if result and result[0] else None


def get_fund_price_date_range(ticker: str) -> tuple[str, str] | None:
    """
    Get the date range of stored prices for a fund.

    Returns:
        Tuple of (oldest_date, newest_date) or None if no prices
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT MIN(date), MAX(date) FROM fund_prices WHERE ticker = ?",
        (ticker.upper().strip(),),
    )
    result = c.fetchone()
    conn.close()
    if result and result[0] and result[1]:
        return (result[0], result[1])
    return None


def get_all_fund_latest_prices() -> dict[str, tuple[str, float]]:
    """
    Get the latest price for all funds in the database.

    Returns:
        Dict mapping ticker -> (date, price)
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT ticker, date, price FROM fund_prices fp1
        WHERE date = (SELECT MAX(date) FROM fund_prices fp2 WHERE fp2.ticker = fp1.ticker)
    """)
    results = c.fetchall()
    conn.close()
    return {row[0]: (row[1], row[2]) for row in results}
