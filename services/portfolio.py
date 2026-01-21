"""
Portfolio service for transaction operations.
"""

from datetime import datetime

import pandas as pd

from core.database import (
    ASSET_TEFAS,
    ASSET_USD_STOCK,
    ASSET_CASH,
    CURRENCY_TRY,
    CURRENCY_USD,
    TX_BUY,
    TX_SELL,
    add_transaction,
    get_portfolio,
    delete_transaction,
    get_unique_tickers,
    get_tickers_with_info,
    get_fund_price_date_range,
    get_all_fund_latest_prices,
    get_fund_prices,
    get_ticker_holdings,
)
from adapters.tefas import fetch_prices_for_new_ticker, update_fund_prices
from adapters.yfinance_stocks import fetch_prices_for_new_stock, update_stock_prices


class PortfolioService:
    """Service for managing portfolio transactions."""

    @staticmethod
    def add_transaction(
        date: str,
        ticker: str,
        quantity: float,
        tax_rate: float,
        notes: str = "",
        asset_type: str = ASSET_TEFAS,
        transaction_type: str = TX_BUY,
        price_per_share: float | None = None,
    ) -> tuple[str, pd.DataFrame]:
        """
        Add a new transaction (buy or sell) with automatic price fetching or manual price entry.

        Args:
            date: Transaction date (may include time, will be truncated to YYYY-MM-DD)
            ticker: Fund/stock ticker symbol or currency for cash (TRY/USD)
            quantity: Number of shares (or amount for cash) - always positive
            tax_rate: Tax rate on gains at sell (0-100)
            notes: Optional notes
            asset_type: TEFAS, USD_STOCK, or CASH
            transaction_type: BUY or SELL
            price_per_share: Optional manual buy price. If None, price is auto-fetched.

        Returns:
            Tuple of (status message, updated portfolio DataFrame)
        """
        if not ticker.strip():
            return "❌ Ticker is required", get_portfolio()
        if quantity <= 0:
            return "❌ Quantity must be positive", get_portfolio()
        if tax_rate < 0 or tax_rate > 100:
            return "❌ Tax rate must be between 0 and 100", get_portfolio()
        if price_per_share is not None and price_per_share <= 0:
            return "❌ Buy price must be positive", get_portfolio()

        # Extract date part
        date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")
        ticker_upper = ticker.upper().strip()
        tx_type = transaction_type.upper() if transaction_type else TX_BUY

        # Determine currency based on asset type
        if asset_type == ASSET_CASH:
            # For cash, ticker IS the currency (TRY or USD)
            currency = ticker_upper if ticker_upper in [CURRENCY_TRY, CURRENCY_USD] else CURRENCY_TRY
            ticker_upper = f"CASH_{currency}"
            result = add_transaction(date_str, ticker_upper, quantity, tax_rate, notes, asset_type, currency, tx_type, price_per_share)
            return result, get_portfolio()

        elif asset_type == ASSET_USD_STOCK:
            currency = CURRENCY_USD
            result = add_transaction(date_str, ticker_upper, quantity, tax_rate, notes, asset_type, currency, tx_type, price_per_share)
            return result, get_portfolio()

        else:
            # TEFAS fund (default)
            currency = CURRENCY_TRY
            result = add_transaction(date_str, ticker_upper, quantity, tax_rate, notes, asset_type, currency, tx_type, price_per_share)
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
    def get_tickers_with_info() -> list[dict]:
        """Get unique tickers with their asset type and currency info."""
        return get_tickers_with_info()

    @staticmethod
    def get_ticker_price_table() -> pd.DataFrame:
        """
        Generate a table with tickers and their latest prices.

        Returns:
            DataFrame with Ticker, Current Price, and Currency columns
        """
        tickers_info = get_tickers_with_info()
        if not tickers_info:
            return pd.DataFrame({"Ticker": ["No tickers"], "Current Price": [0.0], "Currency": [""]})

        latest_prices = get_all_fund_latest_prices()

        rows = []
        for info in tickers_info:
            t = info["ticker"]
            asset_type = info["asset_type"]
            currency = info["currency"]

            # Cash has price = 1
            if asset_type == ASSET_CASH:
                rows.append({"Ticker": t, "Current Price": 1.0, "Currency": currency})
            elif t in latest_prices:
                _, price, curr = latest_prices[t]
                rows.append({"Ticker": t, "Current Price": price, "Currency": curr})
            else:
                rows.append({"Ticker": t, "Current Price": 0.0, "Currency": currency})

        return pd.DataFrame(rows)

    @staticmethod
    def refresh_prices() -> tuple[str, pd.DataFrame]:
        """
        Refresh prices for all tickers in portfolio (TEFAS and US stocks).

        Returns:
            Tuple of (status message, price table DataFrame)
        """
        tickers_info = get_tickers_with_info()
        if not tickers_info:
            return "❌ No tickers in portfolio", pd.DataFrame({"Ticker": ["No tickers"], "Current Price": [0.0], "Currency": [""]})

        results = []
        total_inserted = 0

        for info in tickers_info:
            ticker = info["ticker"]
            asset_type = info["asset_type"]

            # Skip cash - no prices to fetch
            if asset_type == ASSET_CASH:
                results.append(f"✓ {ticker}: cash (no price update needed)")
                continue

            try:
                if asset_type == ASSET_USD_STOCK:
                    inserted, skipped, msg = update_stock_prices(ticker)
                    source = "yfinance"
                else:
                    inserted, skipped, msg = update_fund_prices(ticker)
                    source = "TEFAS"

                total_inserted += inserted
                if inserted > 0:
                    results.append(f"✅ {ticker}: +{inserted} prices ({source})")
                elif "up to date" in msg.lower():
                    results.append(f"✓ {ticker}: up to date")
                elif "No data found" in msg:
                    existing = get_fund_prices(ticker)
                    if existing.empty:
                        results.append(f"⚠️ {ticker}: no price data found")
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

    @staticmethod
    def refresh_tefas_prices() -> tuple[str, pd.DataFrame]:
        """
        Refresh TEFAS prices for all tickers in portfolio.
        Deprecated: Use refresh_prices() instead.

        Returns:
            Tuple of (status message, price table DataFrame)
        """
        return PortfolioService.refresh_prices()
