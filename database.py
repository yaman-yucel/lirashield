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
            price_per_share REAL NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

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

    conn.commit()
    conn.close()


# ============== TRANSACTION FUNCTIONS ==============


def add_transaction(date: str, ticker: str, quantity: float, price: float, notes: str = "") -> str:
    """Add a buy transaction to the database."""
    try:
        valid_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")

        conn = get_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO transactions (date, ticker, quantity, price_per_share, notes) VALUES (?, ?, ?, ?, ?)",
            (valid_date, ticker.upper().strip(), float(quantity), float(price), notes),
        )
        conn.commit()
        conn.close()
        return f"✅ Transaction added: {ticker.upper()} x{quantity} @ {price} TRY on {valid_date}"
    except ValueError:
        return "❌ Error: Date must be in YYYY-MM-DD format"
    except Exception as e:
        return f"❌ Error: {e}"


def get_portfolio() -> pd.DataFrame:
    """Retrieve all transactions as a Pandas DataFrame."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC", conn)
    conn.close()
    return df


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


def get_cpi_usd_rate_for_date(date: str) -> float | None:
    """Get the USD/TRY rate for a specific date. Returns None if not found."""
    conn = get_connection()
    c = conn.cursor()

    # Try exact match first
    c.execute("SELECT usd_try_rate FROM cpi_usd_rates WHERE date = ?", (date,))
    result = c.fetchone()

    if result:
        conn.close()
        return result[0]

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
