"""Tests for TEFAS adapter."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from adapters import tefas


class TestFetchFundPrices:
    """Tests for fetch_fund_prices function."""

    def test_fetch_with_explicit_dates(self, mocker, test_db, sample_tefas_data):
        """Test fetching with explicit start and end dates."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="MAC", start_date="2024-01-01", end_date="2024-01-10")

        assert inserted == 10
        assert skipped == 0  # First insert, nothing to skip
        assert "MAC" in msg
        assert "added" in msg
        mock_crawler.fetch.assert_called_once()

    def test_fetch_with_default_end_date(self, mocker, test_db, sample_tefas_data):
        """Test fetching with default end_date (today)."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="TI2", start_date="2024-01-01")

        assert inserted >= 0  # May vary based on date range
        assert skipped >= 0
        mock_crawler.fetch.assert_called()

    def test_fetch_with_years_back(self, mocker, test_db, sample_tefas_data):
        """Test fetching with years_back parameter."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="MAC", years_back=2)

        assert inserted >= 0  # May vary based on date range
        assert skipped >= 0
        mock_crawler.fetch.assert_called()

    def test_fetch_chunked_requests(self, mocker, test_db):
        """Test that long date ranges are chunked properly."""
        mock_crawler = MagicMock()

        # Create data for multiple chunks
        dates1 = pd.date_range(start="2024-01-01", end="2024-01-30", freq="D")
        data1 = pd.DataFrame({"date": dates1, "price": [100.0] * len(dates1)})

        dates2 = pd.date_range(start="2024-01-31", end="2024-02-29", freq="D")
        data2 = pd.DataFrame({"date": dates2, "price": [101.0] * len(dates2)})

        mock_crawler.fetch.side_effect = [data1, data2]
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        # Fetch 90 days (should be split into 2 chunks of 60 days)
        start_date = "2024-01-01"
        end_date = "2024-03-31"

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="MAC", start_date=start_date, end_date=end_date)

        # Should be called multiple times for chunks
        assert mock_crawler.fetch.call_count >= 2
        assert inserted > 0  # Should have inserted data
        assert skipped >= 0

    def test_fetch_empty_data(self, mocker, test_db):
        """Test handling of empty data from TEFAS."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = pd.DataFrame()
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="INVALID", start_date="2024-01-01", end_date="2024-01-10")

        assert inserted == 0
        assert skipped == 0
        assert "No data found" in msg

    def test_fetch_with_failed_chunks(self, mocker, test_db, sample_tefas_data):
        """Test handling of failed chunks."""
        mock_crawler = MagicMock()
        # First chunk fails, second succeeds
        mock_crawler.fetch.side_effect = [Exception("API error"), sample_tefas_data]
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="MAC", start_date="2024-01-01", end_date="2024-03-31")

        # Should still succeed with the successful chunk
        assert inserted > 0
        assert skipped >= 0

    def test_fetch_ticker_normalization(self, mocker, test_db, sample_tefas_data):
        """Test that ticker is normalized to uppercase."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="  mac  ", start_date="2024-01-01", end_date="2024-01-10")

        # Check that ticker was normalized by querying the database
        from core.database import get_fund_prices

        prices_df = get_fund_prices("MAC")
        assert len(prices_df) > 0
        assert all(prices_df["ticker"] == "MAC")

    def test_fetch_exception_handling(self, mocker, test_db):
        """Test exception handling during fetch."""
        # Make the Crawler constructor itself raise an exception
        mocker.patch("adapters.tefas.Crawler", side_effect=Exception("Network error"))

        inserted, skipped, msg = tefas.fetch_fund_prices(ticker="MAC", start_date="2024-01-01", end_date="2024-01-10")

        assert inserted == 0
        assert skipped == 0
        assert "Error" in msg


class TestUpdateFundPrices:
    """Tests for update_fund_prices function."""

    def test_update_no_existing_data(self, mocker, test_db, sample_tefas_data):
        """Test update when no existing data exists."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.update_fund_prices("MAC")

        assert inserted > 0
        assert skipped >= 0
        assert "MAC" in msg

    def test_update_already_up_to_date(self, mocker, test_db, sample_tefas_data):
        """Test update when data is already up to date."""
        # First insert some recent data
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        # Insert data with recent dates
        today = datetime.now()
        recent_dates = pd.date_range(start=today - timedelta(days=2), end=today, freq="D")
        recent_data = pd.DataFrame({"date": recent_dates, "price": [100.0] * len(recent_dates)})
        mock_crawler.fetch.return_value = recent_data
        tefas.fetch_fund_prices("MAC", start_date=(today - timedelta(days=2)).strftime("%Y-%m-%d"), end_date=today.strftime("%Y-%m-%d"))

        # Now try to update - should be up to date
        inserted, skipped, msg = tefas.update_fund_prices("MAC")

        assert inserted == 0
        assert skipped == 0
        assert "up to date" in msg

    def test_update_with_stale_data(self, mocker, test_db, sample_tefas_data):
        """Test update when data is stale."""
        # First insert old data
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        old_dates = pd.date_range(start=week_ago - timedelta(days=5), end=week_ago, freq="D")
        old_data = pd.DataFrame({"date": old_dates, "price": [100.0] * len(old_dates)})

        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = old_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)
        tefas.fetch_fund_prices("MAC", start_date=(week_ago - timedelta(days=5)).strftime("%Y-%m-%d"), end_date=week_ago.strftime("%Y-%m-%d"))

        # Now add new data
        mock_crawler.fetch.return_value = sample_tefas_data
        inserted, skipped, msg = tefas.update_fund_prices("MAC")

        assert inserted > 0
        assert skipped >= 0
        # Should fetch from day after latest
        call_args = mock_crawler.fetch.call_args
        assert call_args is not None

    def test_update_no_new_data_found(self, mocker, test_db):
        """Test update when no new data is found."""
        # First insert old data
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        old_dates = pd.date_range(start=week_ago - timedelta(days=5), end=week_ago, freq="D")
        old_data = pd.DataFrame({"date": old_dates, "price": [100.0] * len(old_dates)})

        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = old_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)
        tefas.fetch_fund_prices("MAC", start_date=(week_ago - timedelta(days=5)).strftime("%Y-%m-%d"), end_date=week_ago.strftime("%Y-%m-%d"))

        # Now try to update but return empty data
        mock_crawler.fetch.return_value = pd.DataFrame()
        inserted, skipped, msg = tefas.update_fund_prices("MAC")

        assert inserted == 0
        assert skipped == 0
        assert "up to date" in msg


class TestFetchPricesForNewTicker:
    """Tests for fetch_prices_for_new_ticker function."""

    def test_fetch_new_ticker_no_existing_data(self, mocker, test_db, sample_tefas_data):
        """Test fetching for a completely new ticker."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        inserted, skipped, msg = tefas.fetch_prices_for_new_ticker("MAC", "2024-01-01")

        assert inserted > 0
        assert skipped >= 0

    def test_fetch_new_ticker_with_existing_data_after_transaction(self, mocker, test_db, sample_tefas_data):
        """Test fetching when transaction date is after existing data."""
        # First insert some data
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)
        tefas.fetch_fund_prices("MAC", start_date="2024-01-01", end_date="2024-01-10")

        # Now fetch for new ticker with transaction date in the middle
        inserted, skipped, msg = tefas.fetch_prices_for_new_ticker("MAC", "2024-01-05")

        # Should just update (since transaction date is within existing range)
        assert inserted >= 0
        assert skipped >= 0

    def test_fetch_new_ticker_with_existing_data_before_transaction(self, mocker, test_db, sample_tefas_data):
        """Test fetching when transaction date is before existing data."""
        # First insert data starting from 2024-01-10
        mock_crawler = MagicMock()
        later_dates = pd.date_range(start="2024-01-10", end="2024-01-20", freq="D")
        later_data = pd.DataFrame({"date": later_dates, "price": [100.0] * len(later_dates)})
        mock_crawler.fetch.return_value = later_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)
        tefas.fetch_fund_prices("MAC", start_date="2024-01-10", end_date="2024-01-20")

        # Now fetch for transaction date before existing data
        mock_crawler.fetch.return_value = sample_tefas_data
        inserted, skipped, msg = tefas.fetch_prices_for_new_ticker("MAC", "2024-01-01")

        assert inserted > 0
        assert skipped >= 0


class TestGetCurrentPrice:
    """Tests for get_current_price function."""

    def test_get_current_price_recent_data(self, mocker, test_db):
        """Test getting price when data is recent."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        # Insert recent data
        recent_dates = pd.date_range(start=yesterday, end=yesterday, freq="D")
        recent_data = pd.DataFrame({"date": recent_dates, "price": [100.5] * len(recent_dates)})

        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = recent_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)
        tefas.fetch_fund_prices("MAC", start_date=yesterday.strftime("%Y-%m-%d"), end_date=yesterday.strftime("%Y-%m-%d"))

        price = tefas.get_current_price("MAC")

        assert price == 100.5

    def test_get_current_price_stale_data(self, mocker, test_db, sample_tefas_data):
        """Test getting price when data is stale and needs update."""
        today = datetime.now()
        week_ago = today - timedelta(days=7)

        # Insert old data
        old_dates = pd.date_range(start=week_ago, end=week_ago, freq="D")
        old_data = pd.DataFrame({"date": old_dates, "price": [100.0] * len(old_dates)})

        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = old_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)
        tefas.fetch_fund_prices("MAC", start_date=week_ago.strftime("%Y-%m-%d"), end_date=week_ago.strftime("%Y-%m-%d"))

        # Now return new data when updating
        new_dates = pd.date_range(start=today, end=today, freq="D")
        new_data = pd.DataFrame({"date": new_dates, "price": [101.0] * len(new_dates)})
        mock_crawler.fetch.return_value = new_data

        price = tefas.get_current_price("MAC")

        assert price == 101.0

    def test_get_current_price_no_data(self, mocker, test_db):
        """Test getting price when no data exists."""
        # Don't insert any data, and make fetch return empty
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = pd.DataFrame()
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        price = tefas.get_current_price("MAC")

        assert price is None


class TestIsValidTefasFund:
    """Tests for is_valid_tefas_fund function."""

    def test_valid_fund(self, mocker, sample_tefas_data):
        """Test validation of a valid fund."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        result = tefas.is_valid_tefas_fund("MAC")

        assert result is True

    def test_invalid_fund(self, mocker):
        """Test validation of an invalid fund."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = pd.DataFrame()
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        result = tefas.is_valid_tefas_fund("INVALID")

        assert result is False

    def test_invalid_fund_exception(self, mocker):
        """Test validation when exception occurs."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.side_effect = Exception("API error")
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        result = tefas.is_valid_tefas_fund("INVALID")

        assert result is False

    def test_ticker_normalization(self, mocker, sample_tefas_data):
        """Test that ticker is normalized during validation."""
        mock_crawler = MagicMock()
        mock_crawler.fetch.return_value = sample_tefas_data
        mocker.patch("adapters.tefas.Crawler", return_value=mock_crawler)

        result = tefas.is_valid_tefas_fund("  mac  ")

        assert result is True
        # Verify ticker was normalized in the call
        call_args = mock_crawler.fetch.call_args
        assert call_args.kwargs["name"] == "MAC"
