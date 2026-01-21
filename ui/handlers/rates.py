"""
Rate handlers for Gradio UI (USD/TRY and CPI).
"""

import pandas as pd

from services import RatesService


# ============== USD/TRY RATE HANDLERS ==============


def handle_add_rate(date: str, rate: float, notes: str) -> tuple[str, pd.DataFrame]:
    """Handle adding a new CPI/USD rate."""
    return RatesService.add_usd_rate(date, rate, notes)


def handle_delete_rate(rate_id: int) -> tuple[str, pd.DataFrame]:
    """Handle deleting a CPI/USD rate."""
    return RatesService.delete_usd_rate(rate_id)


def handle_fetch_rate(date: str) -> tuple[str, pd.DataFrame]:
    """Fetch USD/TRY rate from yfinance and add to database."""
    return RatesService.fetch_usd_rate(date)


def handle_bulk_import(csv_text: str) -> tuple[str, pd.DataFrame]:
    """Handle bulk import of CPI/USD rates."""
    return RatesService.bulk_import_usd_rates(csv_text)


def refresh_rates() -> pd.DataFrame:
    """Refresh the rates table."""
    return RatesService.get_usd_rates()


def handle_refresh_all_usd_rates() -> tuple[str, pd.DataFrame]:
    """Fetch all USD/TRY rates from earliest needed date to today."""
    return RatesService.refresh_all_usd_rates()


def handle_quick_refresh_usd_rates() -> tuple[str, pd.DataFrame]:
    """Quick refresh: Fetch only missing USD/TRY rates from latest stored date to today."""
    return RatesService.quick_refresh_usd_rates()


# ============== OFFICIAL CPI HANDLERS (TCMB) ==============


def handle_add_cpi(year_month: str, cpi_yoy: float, cpi_mom: float, notes: str) -> tuple[str, pd.DataFrame]:
    """Handle adding official CPI data."""
    return RatesService.add_cpi(year_month, cpi_yoy, cpi_mom, notes)


def handle_delete_cpi(cpi_id: int) -> tuple[str, pd.DataFrame]:
    """Handle deleting a CPI entry."""
    return RatesService.delete_cpi(cpi_id)


def handle_bulk_import_cpi(csv_text: str) -> tuple[str, pd.DataFrame]:
    """Handle bulk import of CPI data."""
    return RatesService.bulk_import_cpi(csv_text)


def refresh_cpi() -> pd.DataFrame:
    """Refresh the CPI table."""
    return RatesService.get_cpi_data()
