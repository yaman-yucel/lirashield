"""
Rates service for CPI and USD/TRY rate operations.
"""

from datetime import datetime

import pandas as pd

from core.database import (
    add_cpi_usd_rate,
    get_cpi_usd_rates,
    delete_cpi_usd_rate,
    bulk_import_cpi_usd_rates,
    add_cpi_official,
    get_cpi_official_data,
    delete_cpi_official,
    bulk_import_cpi_official,
)
from core.analysis import (
    fetch_usd_rate_from_yfinance,
    fetch_all_usd_rates,
    fetch_missing_usd_rates,
)


class RatesService:
    """Service for managing CPI and USD/TRY rates."""

    # ============== USD/TRY RATES ==============

    @staticmethod
    def add_usd_rate(date: str, rate: float, notes: str = "") -> tuple[str, pd.DataFrame]:
        """
        Add a USD/TRY rate manually.

        Args:
            date: Rate date (may include time, will be truncated to YYYY-MM-DD)
            rate: USD/TRY exchange rate
            notes: Optional notes

        Returns:
            Tuple of (status message, updated rates DataFrame)
        """
        if rate <= 0:
            return "❌ Rate must be positive", get_cpi_usd_rates()

        date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")
        result = add_cpi_usd_rate(date_str, rate, source="manual", notes=notes)
        return result, get_cpi_usd_rates()

    @staticmethod
    def delete_usd_rate(rate_id: int) -> tuple[str, pd.DataFrame]:
        """
        Delete a USD/TRY rate by ID.

        Args:
            rate_id: ID of rate to delete

        Returns:
            Tuple of (status message, updated rates DataFrame)
        """
        if rate_id <= 0:
            return "❌ Enter a valid rate ID", get_cpi_usd_rates()
        result = delete_cpi_usd_rate(int(rate_id))
        return result, get_cpi_usd_rates()

    @staticmethod
    def fetch_usd_rate(date: str) -> tuple[str, pd.DataFrame]:
        """
        Fetch USD/TRY rate from yfinance and store in database.

        Args:
            date: Date to fetch rate for

        Returns:
            Tuple of (status message, updated rates DataFrame)
        """
        date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")

        rate = fetch_usd_rate_from_yfinance(date_str)
        if rate:
            result = add_cpi_usd_rate(date_str, rate, source="yfinance", notes="Fetched automatically")
            return result, get_cpi_usd_rates()
        return f"❌ Could not fetch rate for {date_str}. Try a different date or enter manually.", get_cpi_usd_rates()

    @staticmethod
    def bulk_import_usd_rates(csv_text: str) -> tuple[str, pd.DataFrame]:
        """
        Bulk import USD/TRY rates from CSV format.

        Args:
            csv_text: CSV data with date,rate format

        Returns:
            Tuple of (status message, updated rates DataFrame)
        """
        result = bulk_import_cpi_usd_rates(csv_text)
        return result, get_cpi_usd_rates()

    @staticmethod
    def refresh_all_usd_rates() -> tuple[str, pd.DataFrame]:
        """
        Fetch all USD/TRY rates from earliest needed date to today.

        Returns:
            Tuple of (status message, updated rates DataFrame)
        """
        new_count, total_count, status = fetch_all_usd_rates()
        return status, get_cpi_usd_rates()

    @staticmethod
    def quick_refresh_usd_rates() -> tuple[str, pd.DataFrame]:
        """
        Quick refresh: Fetch only missing USD/TRY rates from latest stored date to today.

        Returns:
            Tuple of (status message, updated rates DataFrame)
        """
        new_count, total_count, status = fetch_missing_usd_rates()
        return status, get_cpi_usd_rates()

    @staticmethod
    def get_usd_rates() -> pd.DataFrame:
        """Get all USD/TRY rates."""
        return get_cpi_usd_rates()

    # ============== OFFICIAL CPI ==============

    @staticmethod
    def add_cpi(year_month: str, cpi_yoy: float, cpi_mom: float, notes: str = "") -> tuple[str, pd.DataFrame]:
        """
        Add official CPI data.

        Args:
            year_month: Month in YYYY-MM format
            cpi_yoy: Year-over-Year inflation rate
            cpi_mom: Month-over-Month inflation rate
            notes: Optional notes

        Returns:
            Tuple of (status message, updated CPI DataFrame)
        """
        if cpi_yoy <= 0:
            return "❌ YoY rate must be positive", get_cpi_official_data()
        result = add_cpi_official(year_month, cpi_yoy, cpi_mom if cpi_mom != 0 else None, notes)
        return result, get_cpi_official_data()

    @staticmethod
    def delete_cpi(cpi_id: int) -> tuple[str, pd.DataFrame]:
        """
        Delete a CPI entry by ID.

        Args:
            cpi_id: ID of CPI entry to delete

        Returns:
            Tuple of (status message, updated CPI DataFrame)
        """
        if cpi_id <= 0:
            return "❌ Enter a valid CPI ID", get_cpi_official_data()
        result = delete_cpi_official(int(cpi_id))
        return result, get_cpi_official_data()

    @staticmethod
    def bulk_import_cpi(csv_text: str) -> tuple[str, pd.DataFrame]:
        """
        Bulk import CPI data from CSV format.

        Args:
            csv_text: CSV data with year_month,yoy,mom format

        Returns:
            Tuple of (status message, updated CPI DataFrame)
        """
        result = bulk_import_cpi_official(csv_text)
        return result, get_cpi_official_data()

    @staticmethod
    def get_cpi_data() -> pd.DataFrame:
        """Get all official CPI data."""
        return get_cpi_official_data()
