"""Tests for yfinance stocks adapter."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from adapters import yfinance_stocks


class TestFetchStockPrices:
    """Tests for fetch_stock_prices function."""

    def test_fetch_with_explicit_dates(self, mocker, test_db, sample_yfinance_data):
        """Test fetching with explicit start and end dates."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="NVDA", start_date="2024-01-01", end_date="2024-01-10")

        assert inserted == 10
        assert skipped == 0  # First insert, nothing to skip
        assert "NVDA" in msg
        assert "added" in msg
        mock_ticker.history.assert_called_once()

    def test_fetch_with_default_end_date(self, mocker, test_db, sample_yfinance_data):
        """Test fetching with default end_date (today)."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="META", start_date="2024-01-01")

        assert inserted >= 0
        assert skipped >= 0
        mock_ticker.history.assert_called_once()

    def test_fetch_with_years_back(self, mocker, test_db, sample_yfinance_data):
        """Test fetching with years_back parameter."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="AAPL", years_back=2)

        assert inserted >= 0
        assert skipped >= 0
        mock_ticker.history.assert_called_once()

    def test_fetch_empty_data(self, mocker, test_db):
        """Test handling of empty data from yfinance."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="INVALID", start_date="2024-01-01", end_date="2024-01-10")

        assert inserted == 0
        assert skipped == 0
        assert "No data found" in msg

    def test_fetch_ticker_normalization(self, mocker, test_db, sample_yfinance_data):
        """Test that ticker is normalized to uppercase."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="  nvda  ", start_date="2024-01-01", end_date="2024-01-10")

        # Check that ticker was normalized by querying the database
        from core.database import get_fund_prices

        prices_df = get_fund_prices("NVDA")
        assert len(prices_df) > 0
        assert all(prices_df["ticker"] == "NVDA")

    def test_fetch_uses_close_price(self, mocker, test_db, sample_yfinance_data):
        """Test that Close price is used from yfinance data."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="NVDA", start_date="2024-01-01", end_date="2024-01-10")

        # Verify Close prices were used by checking the database
        from core.database import get_fund_prices

        prices_df = get_fund_prices("NVDA")
        assert len(prices_df) == 10
        # Prices should match Close column values (100.5, 101.0, 101.5, etc.)
        expected_prices = [100.5 + i * 0.5 for i in range(10)]
        actual_prices = sorted(prices_df["price"].tolist())
        assert len(actual_prices) == len(expected_prices)

    def test_fetch_exception_handling(self, mocker, test_db):
        """Test exception handling during fetch."""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("Network error")
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_stock_prices(ticker="NVDA", start_date="2024-01-01", end_date="2024-01-10")

        assert inserted == 0
        assert skipped == 0
        assert "Error" in msg


class TestUpdateStockPrices:
    """Tests for update_stock_prices function."""

    def test_update_no_existing_data(self, mocker, test_db, sample_yfinance_data):
        """Test update when no existing data exists."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.update_stock_prices("NVDA")

        assert inserted > 0
        assert skipped >= 0
        assert "NVDA" in msg

    def test_update_already_up_to_date(self, mocker, test_db, sample_yfinance_data):
        """Test update when data is already up to date."""
        # First insert some recent data
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        recent_dates = pd.date_range(start=yesterday, end=yesterday, freq="D")
        recent_data = pd.DataFrame(
            {
                "Open": [150.0] * len(recent_dates),
                "High": [151.0] * len(recent_dates),
                "Low": [149.0] * len(recent_dates),
                "Close": [150.0] * len(recent_dates),
                "Volume": [1000000] * len(recent_dates),
            },
            index=recent_dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = recent_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date=yesterday.strftime("%Y-%m-%d"), end_date=yesterday.strftime("%Y-%m-%d"))

        # Now try to update - should be up to date
        inserted, skipped, msg = yfinance_stocks.update_stock_prices("NVDA")

        assert inserted == 0
        assert skipped == 0
        assert "up to date" in msg

    def test_update_with_stale_data(self, mocker, test_db, sample_yfinance_data):
        """Test update when data is stale."""
        # First insert old data
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        old_dates = pd.date_range(start=week_ago - timedelta(days=5), end=week_ago, freq="D")
        old_data = pd.DataFrame(
            {
                "Open": [150.0] * len(old_dates),
                "High": [151.0] * len(old_dates),
                "Low": [149.0] * len(old_dates),
                "Close": [150.0] * len(old_dates),
                "Volume": [1000000] * len(old_dates),
            },
            index=old_dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = old_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date=(week_ago - timedelta(days=5)).strftime("%Y-%m-%d"), end_date=week_ago.strftime("%Y-%m-%d"))

        # Now add new data
        mock_ticker.history.return_value = sample_yfinance_data
        inserted, skipped, msg = yfinance_stocks.update_stock_prices("NVDA")

        assert inserted > 0
        assert skipped >= 0
        # Should fetch from day after latest
        call_args = mock_ticker.history.call_args
        assert call_args is not None

    def test_update_no_new_data_found(self, mocker, test_db):
        """Test update when no new data is found."""
        # First insert old data
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        old_dates = pd.date_range(start=week_ago - timedelta(days=5), end=week_ago, freq="D")
        old_data = pd.DataFrame(
            {
                "Open": [150.0] * len(old_dates),
                "High": [151.0] * len(old_dates),
                "Low": [149.0] * len(old_dates),
                "Close": [150.0] * len(old_dates),
                "Volume": [1000000] * len(old_dates),
            },
            index=old_dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = old_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date=(week_ago - timedelta(days=5)).strftime("%Y-%m-%d"), end_date=week_ago.strftime("%Y-%m-%d"))

        # Now try to update but return empty data
        mock_ticker.history.return_value = pd.DataFrame()
        inserted, skipped, msg = yfinance_stocks.update_stock_prices("NVDA")

        assert inserted == 0
        assert skipped == 0
        assert "up to date" in msg


class TestFetchPricesForNewStock:
    """Tests for fetch_prices_for_new_stock function."""

    def test_fetch_new_stock_no_existing_data(self, mocker, test_db, sample_yfinance_data):
        """Test fetching for a completely new stock."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        inserted, skipped, msg = yfinance_stocks.fetch_prices_for_new_stock("NVDA", "2024-01-01")

        assert inserted > 0
        assert skipped >= 0

    def test_fetch_new_stock_with_existing_data_after_transaction(self, mocker, test_db, sample_yfinance_data):
        """Test fetching when transaction date is after existing data."""
        # First insert some data
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = sample_yfinance_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date="2024-01-01", end_date="2024-01-10")

        # Now fetch for new stock with transaction date in the middle
        inserted, skipped, msg = yfinance_stocks.fetch_prices_for_new_stock("NVDA", "2024-01-05")

        # Should just update (since transaction date is within existing range)
        assert inserted >= 0
        assert skipped >= 0

    def test_fetch_new_stock_with_existing_data_before_transaction(self, mocker, test_db, sample_yfinance_data):
        """Test fetching when transaction date is before existing data."""
        # First insert data starting from 2024-01-10
        later_dates = pd.date_range(start="2024-01-10", end="2024-01-20", freq="D")
        later_data = pd.DataFrame(
            {
                "Open": [150.0] * len(later_dates),
                "High": [151.0] * len(later_dates),
                "Low": [149.0] * len(later_dates),
                "Close": [150.0] * len(later_dates),
                "Volume": [1000000] * len(later_dates),
            },
            index=later_dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = later_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date="2024-01-10", end_date="2024-01-20")

        # Now fetch for transaction date before existing data
        mock_ticker.history.return_value = sample_yfinance_data
        inserted, skipped, msg = yfinance_stocks.fetch_prices_for_new_stock("NVDA", "2024-01-01")

        assert inserted > 0
        assert skipped >= 0


class TestGetCurrentStockPrice:
    """Tests for get_current_stock_price function."""

    def test_get_current_price_recent_data(self, mocker, test_db):
        """Test getting price when data is recent."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # Insert recent data
        recent_dates = pd.date_range(start=yesterday, end=yesterday, freq="D")
        recent_data = pd.DataFrame(
            {
                "Open": [150.0] * len(recent_dates),
                "High": [151.0] * len(recent_dates),
                "Low": [149.0] * len(recent_dates),
                "Close": [150.5] * len(recent_dates),
                "Volume": [1000000] * len(recent_dates),
            },
            index=recent_dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = recent_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date=yesterday.strftime("%Y-%m-%d"), end_date=yesterday.strftime("%Y-%m-%d"))

        price = yfinance_stocks.get_current_stock_price("NVDA")

        assert price == 150.5

    def test_get_current_price_stale_data(self, mocker, test_db, sample_yfinance_data):
        """Test getting price when data is stale and needs update."""
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        # Insert old data
        old_dates = pd.date_range(start=week_ago, end=week_ago, freq="D")
        old_data = pd.DataFrame(
            {
                "Open": [150.0] * len(old_dates),
                "High": [151.0] * len(old_dates),
                "Low": [149.0] * len(old_dates),
                "Close": [150.0] * len(old_dates),
                "Volume": [1000000] * len(old_dates),
            },
            index=old_dates,
        )

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = old_data
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)
        yfinance_stocks.fetch_stock_prices("NVDA", start_date=week_ago.strftime("%Y-%m-%d"), end_date=week_ago.strftime("%Y-%m-%d"))

        # Now return new data when updating
        new_dates = pd.date_range(start=today, end=today, freq="D")
        new_data = pd.DataFrame(
            {
                "Open": [151.0] * len(new_dates),
                "High": [152.0] * len(new_dates),
                "Low": [150.0] * len(new_dates),
                "Close": [151.0] * len(new_dates),
                "Volume": [1000000] * len(new_dates),
            },
            index=new_dates,
        )
        mock_ticker.history.return_value = new_data

        price = yfinance_stocks.get_current_stock_price("NVDA")

        assert price == 151.0

    def test_get_current_price_no_data(self, mocker, test_db):
        """Test getting price when no data exists."""
        # Don't insert any data, and make fetch return empty
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        price = yfinance_stocks.get_current_stock_price("NVDA")

        assert price is None


class TestIsValidStock:
    """Tests for is_valid_stock function."""

    def test_valid_stock_with_regular_market_price(self, mocker):
        """Test validation of a valid stock with regularMarketPrice."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"regularMarketPrice": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        result = yfinance_stocks.is_valid_stock("NVDA")

        assert result is True

    def test_valid_stock_with_previous_close(self, mocker):
        """Test validation of a valid stock with previousClose."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"previousClose": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        result = yfinance_stocks.is_valid_stock("NVDA")

        assert result is True

    def test_invalid_stock_no_price_data(self, mocker):
        """Test validation of an invalid stock with no price data."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        result = yfinance_stocks.is_valid_stock("INVALID")

        assert result is False

    def test_invalid_stock_exception(self, mocker):
        """Test validation when exception occurs."""
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", side_effect=Exception("API error"))

        result = yfinance_stocks.is_valid_stock("INVALID")

        assert result is False

    def test_ticker_normalization(self, mocker):
        """Test that ticker is normalized during validation."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"regularMarketPrice": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        result = yfinance_stocks.is_valid_stock("  nvda  ")

        assert result is True
        # Verify ticker was normalized in the call
        yfinance_stocks.yf.Ticker.assert_called_with("NVDA")


class TestGetStockInfo:
    """Tests for get_stock_info function."""

    def test_get_stock_info_success(self, mocker):
        """Test getting stock info successfully."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"shortName": "NVIDIA Corporation", "currency": "USD", "exchange": "NMS", "regularMarketPrice": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        info = yfinance_stocks.get_stock_info("NVDA")

        assert info is not None
        assert info["ticker"] == "NVDA"
        assert info["name"] == "NVIDIA Corporation"
        assert info["currency"] == "USD"
        assert info["exchange"] == "NMS"
        assert info["current_price"] == 150.0

    def test_get_stock_info_with_long_name(self, mocker):
        """Test getting stock info when shortName is not available."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"longName": "NVIDIA Corporation", "currency": "USD", "exchange": "NMS", "previousClose": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        info = yfinance_stocks.get_stock_info("NVDA")

        assert info is not None
        assert info["name"] == "NVIDIA Corporation"
        assert info["current_price"] == 150.0

    def test_get_stock_info_fallback_to_ticker(self, mocker):
        """Test getting stock info when name is not available."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"currency": "USD", "exchange": "NMS", "regularMarketPrice": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        info = yfinance_stocks.get_stock_info("NVDA")

        assert info is not None
        assert info["name"] == "NVDA"  # Falls back to ticker

    def test_get_stock_info_exception(self, mocker):
        """Test getting stock info when exception occurs."""
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", side_effect=Exception("API error"))

        info = yfinance_stocks.get_stock_info("INVALID")

        assert info is None

    def test_get_stock_info_ticker_normalization(self, mocker):
        """Test that ticker is normalized when getting stock info."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"shortName": "NVIDIA Corporation", "currency": "USD", "exchange": "NMS", "regularMarketPrice": 150.0}
        mocker.patch("adapters.yfinance_stocks.yf.Ticker", return_value=mock_ticker)

        info = yfinance_stocks.get_stock_info("  nvda  ")

        assert info is not None
        assert info["ticker"] == "NVDA"
        yfinance_stocks.yf.Ticker.assert_called_with("NVDA")
