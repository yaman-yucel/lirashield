"""
Portfolio service for transaction operations.
"""

from datetime import datetime

import pandas as pd

from core.database import (
    add_transaction,
    get_portfolio,
    delete_transaction,
    get_unique_tickers,
    get_fund_price_date_range,
    get_all_fund_latest_prices,
    get_fund_prices,
)
from adapters.tefas import fetch_prices_for_new_ticker, update_fund_prices


class PortfolioService:
    """Service for managing portfolio transactions."""

    @staticmethod
    def add_transaction(date: str, ticker: str, quantity: float, tax_rate: float, notes: str = "") -> tuple[str, pd.DataFrame]:
        """
        Add a new transaction with automatic TEFAS price fetching.

        Args:
            date: Purchase date (may include time, will be truncated to YYYY-MM-DD)
            ticker: Fund ticker symbol
            quantity: Number of shares
            tax_rate: Tax rate on TRY gains at sell (0-100)
            notes: Optional notes

        Returns:
            Tuple of (status message, updated portfolio DataFrame)
        """
        if not ticker.strip():
            return "❌ Ticker is required", get_portfolio()
        if quantity <= 0:
            return "❌ Quantity must be positive", get_portfolio()
        if tax_rate < 0 or tax_rate > 100:
            return "❌ Tax rate must be between 0 and 100", get_portfolio()

        # Extract date part
        date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")
        ticker_upper = ticker.upper().strip()

        # Ensure we have TEFAS prices for this ticker
        existing_range = get_fund_price_date_range(ticker_upper)
        tefas_status = ""

        if existing_range is None:
            # New ticker - fetch historical prices first
            try:
                inserted, skipped, tefas_msg = fetch_prices_for_new_ticker(ticker_upper, date_str)
                if inserted > 0:
                    tefas_status = f"📈 TEFAS: {inserted} prices fetched"
                elif "No data found" in tefas_msg or (inserted == 0 and skipped == 0):
                    return f"❌ {ticker_upper} is not a valid TEFAS fund. Cannot add transaction.", get_portfolio()
            except Exception as e:
                return f"❌ Failed to fetch TEFAS prices: {e}", get_portfolio()
        else:
            # Update prices to ensure we have the latest
            update_fund_prices(ticker_upper)

        # Add transaction (will look up price from fund_prices)
        result = add_transaction(date_str, ticker_upper, quantity, tax_rate, notes)

        if result.startswith("✅") and tefas_status:
            result += f"\n{tefas_status}"

        return result, get_portfolio()

    @staticmethod
    def delete_transaction(transaction_id: int) -> tuple[str, pd.DataFrame]:
        """
        Delete a transaction by ID.

        Args:
            transaction_id: ID of transaction to delete

        Returns:
            Tuple of (status message, updated portfolio DataFrame)
        """
        if transaction_id <= 0:
            return "❌ Enter a valid transaction ID", get_portfolio()
        result = delete_transaction(int(transaction_id))
        return result, get_portfolio()

    @staticmethod
    def get_portfolio() -> pd.DataFrame:
        """Get all transactions with buy prices."""
        return get_portfolio()

    @staticmethod
    def get_unique_tickers() -> list[str]:
        """Get list of unique tickers in portfolio."""
        return get_unique_tickers()

    @staticmethod
    def get_ticker_price_table() -> pd.DataFrame:
        """
        Generate a table with tickers and their latest prices.

        Returns:
            DataFrame with Ticker and Current Price columns
        """
        tickers = get_unique_tickers()
        if not tickers:
            return pd.DataFrame({"Ticker": ["No tickers"], "Current Price": [0.0]})

        latest_prices = get_all_fund_latest_prices()

        prices = []
        for t in tickers:
            if t in latest_prices:
                _, price = latest_prices[t]
                prices.append(price)
            else:
                prices.append(0.0)

        return pd.DataFrame({"Ticker": tickers, "Current Price": prices})

    @staticmethod
    def refresh_tefas_prices() -> tuple[str, pd.DataFrame]:
        """
        Refresh TEFAS prices for all tickers in portfolio.

        Returns:
            Tuple of (status message, price table DataFrame)
        """
        tickers = get_unique_tickers()
        if not tickers:
            return "❌ No tickers in portfolio", pd.DataFrame({"Ticker": ["No tickers"], "Current Price": [0.0]})

        results = []
        total_inserted = 0

        for ticker in tickers:
            try:
                inserted, skipped, msg = update_fund_prices(ticker)
                total_inserted += inserted
                if inserted > 0:
                    results.append(f"✅ {ticker}: +{inserted} prices")
                elif "up to date" in msg.lower():
                    results.append(f"✓ {ticker}: up to date")
                elif "No data found" in msg:
                    existing = get_fund_prices(ticker)
                    if existing.empty:
                        results.append(f"⚠️ {ticker}: not a TEFAS fund")
                    else:
                        results.append(f"✓ {ticker}: up to date ({len(existing)} prices stored)")
                else:
                    results.append(f"⚠️ {ticker}: {msg}")
            except Exception as e:
                results.append(f"❌ {ticker}: {e}")

        # Get updated price table
        price_table = PortfolioService.get_ticker_price_table()
        status = f"📈 Updated {total_inserted} prices\n" + "\n".join(results)

        return status, price_table
