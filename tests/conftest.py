"""Shared pytest fixtures and configuration."""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd


@pytest.fixture
def test_db(mocker):
    """Create a temporary test database and patch settings.database_path to use it."""
    # Create a temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Patch settings.database_path in the config module
    mocker.patch("core.config.settings.database_path", db_path)

    # Initialize the database
    from core.database import init_db

    init_db()

    yield db_path

    # Cleanup: remove the temporary database file
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def sample_date_range():
    """Provide sample date strings for testing."""
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    year_ago = today - timedelta(days=365)

    return {
        "today": today.strftime("%Y-%m-%d"),
        "week_ago": week_ago.strftime("%Y-%m-%d"),
        "month_ago": month_ago.strftime("%Y-%m-%d"),
        "year_ago": year_ago.strftime("%Y-%m-%d"),
    }


@pytest.fixture
def sample_tefas_data():
    """Create sample TEFAS DataFrame for testing."""
    dates = pd.date_range(start="2024-01-01", end="2024-01-10", freq="D")
    data = pd.DataFrame({"date": dates, "price": [100.0 + i * 0.5 for i in range(len(dates))]})
    return data


@pytest.fixture
def sample_yfinance_data():
    """Create sample yfinance DataFrame for testing."""
    dates = pd.date_range(start="2024-01-01", end="2024-01-10", freq="D")
    data = pd.DataFrame(
        {
            "Open": [100.0 + i * 0.5 for i in range(len(dates))],
            "High": [101.0 + i * 0.5 for i in range(len(dates))],
            "Low": [99.0 + i * 0.5 for i in range(len(dates))],
            "Close": [100.5 + i * 0.5 for i in range(len(dates))],
            "Volume": [1000000] * len(dates),
        },
        index=dates,
    )
    return data
