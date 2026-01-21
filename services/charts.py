"""
Charts service for generating fund price charts.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.database import get_fund_prices
from core.analysis import fetch_usd_rates_for_date_range, get_usd_rates_as_dataframe


class ChartsService:
    """Service for generating fund price charts."""

    @staticmethod
    def generate_fund_chart(ticker: str, auto_fetch_usd: bool, base_date: str | None = None) -> tuple[go.Figure | None, str]:
        """
        Generate a dual-axis chart showing fund price in both TRY and USD terms.

        Args:
            ticker: Fund ticker symbol
            auto_fetch_usd: Whether to auto-fetch missing USD rates
            base_date: Optional start date to filter data from (YYYY-MM-DD)

        Returns:
            Tuple of (plotly figure, status message)
        """
        if not ticker or not ticker.strip():
            return None, "❌ Please select a fund ticker"

        ticker = ticker.upper().strip()

        # Get fund prices
        prices_df = get_fund_prices(ticker)
        if prices_df.empty:
            return None, f"❌ No price data found for {ticker}"

        # Sort by date ascending for charting
        prices_df = prices_df.sort_values("date", ascending=True)

        # Filter by base date if provided
        if base_date:
            base_date_str = str(base_date)[:10]
            prices_df = prices_df[prices_df["date"] >= base_date_str]
            if prices_df.empty:
                return None, f"❌ No price data found for {ticker} from {base_date_str}"

        # Get date range
        start_date = prices_df["date"].min()
        end_date = prices_df["date"].max()

        # Fetch USD rates for this date range if auto_fetch is enabled
        if auto_fetch_usd:
            count, msg = fetch_usd_rates_for_date_range(start_date, end_date)
            status_parts = [msg] if count > 0 else []
        else:
            status_parts = []

        # Get USD rates
        usd_df = get_usd_rates_as_dataframe(start_date, end_date)

        # Merge fund prices with USD rates
        prices_df["date"] = pd.to_datetime(prices_df["date"])
        if not usd_df.empty:
            usd_df["date"] = pd.to_datetime(usd_df["date"])
            merged_df = pd.merge_asof(prices_df.sort_values("date"), usd_df.sort_values("date"), on="date", direction="backward")
        else:
            merged_df = prices_df.copy()
            merged_df["usd_try_rate"] = None

        # Calculate USD price where we have rates
        merged_df["price_usd"] = None
        if "usd_try_rate" in merged_df.columns:
            mask = merged_df["usd_try_rate"].notna() & (merged_df["usd_try_rate"] > 0)
            merged_df.loc[mask, "price_usd"] = merged_df.loc[mask, "price"] / merged_df.loc[mask, "usd_try_rate"]

        # Create dual-axis chart
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # TRY price line
        fig.add_trace(
            go.Scatter(
                x=merged_df["date"],
                y=merged_df["price"],
                name=f"{ticker} (TRY)",
                line=dict(color="#2E86AB", width=2),
                hovertemplate="%{x|%Y-%m-%d}<br>TRY: %{y:.4f}<extra></extra>",
            ),
            secondary_y=False,
        )

        # USD price line (where available)
        usd_data = merged_df[merged_df["price_usd"].notna()]
        if not usd_data.empty:
            fig.add_trace(
                go.Scatter(
                    x=usd_data["date"],
                    y=usd_data["price_usd"],
                    name=f"{ticker} (USD)",
                    line=dict(color="#A23B72", width=2),
                    hovertemplate="%{x|%Y-%m-%d}<br>USD: $%{y:.6f}<extra></extra>",
                ),
                secondary_y=True,
            )

        # Update layout
        fig.update_layout(
            title=dict(text=f"📈 {ticker} Price History", font=dict(size=20)),
            xaxis_title="Date",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            template="plotly_white",
            height=500,
        )

        fig.update_yaxes(title_text="Price (TRY)", secondary_y=False, tickformat=".4f")
        fig.update_yaxes(title_text="Price (USD)", secondary_y=True, tickformat="$.6f")

        # Build status message
        total_prices = len(prices_df)
        usd_prices = len(usd_data)
        status_parts.append(f"📊 {ticker}: {total_prices} price points, {usd_prices} with USD conversion")

        if usd_prices < total_prices:
            missing = total_prices - usd_prices
            status_parts.append(f"⚠️ {missing} dates missing USD rates")

        return fig, "\n".join(status_parts)

    @staticmethod
    def generate_normalized_chart(tickers_str: str, auto_fetch_usd: bool, show_usd: bool, base_date: str | None = None) -> tuple[go.Figure | None, str]:
        """
        Generate a normalized comparison chart for multiple funds.
        All funds are normalized to 100 at the base date for easy comparison.

        Args:
            tickers_str: Comma-separated list of tickers
            auto_fetch_usd: Whether to auto-fetch missing USD rates
            show_usd: Whether to show USD-denominated values
            base_date: Optional base date for normalization (YYYY-MM-DD)

        Returns:
            Tuple of (plotly figure, status message)
        """
        if not tickers_str or not tickers_str.strip():
            return None, "❌ Please enter at least one ticker"

        tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
        if not tickers:
            return None, "❌ Please enter at least one ticker"

        # Parse base date if provided
        base_date_str = str(base_date)[:10] if base_date else None

        fig = go.Figure()
        status_parts = []
        colors = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3B1F2B", "#95190C"]

        # Find overall date range
        all_dates = []
        for ticker in tickers:
            prices_df = get_fund_prices(ticker)
            if not prices_df.empty:
                if base_date_str:
                    prices_df = prices_df[prices_df["date"] >= base_date_str]
                if not prices_df.empty:
                    all_dates.extend(prices_df["date"].tolist())

        if not all_dates:
            return None, "❌ No price data found for any ticker" + (f" from {base_date_str}" if base_date_str else "")

        start_date = min(all_dates)
        end_date = max(all_dates)

        # Fetch USD rates if needed
        if auto_fetch_usd and show_usd:
            count, msg = fetch_usd_rates_for_date_range(start_date, end_date)
            if count > 0:
                status_parts.append(msg)

        # Get USD rates
        usd_df = get_usd_rates_as_dataframe(start_date, end_date)
        if not usd_df.empty:
            usd_df["date"] = pd.to_datetime(usd_df["date"])

        for i, ticker in enumerate(tickers):
            prices_df = get_fund_prices(ticker)
            if prices_df.empty:
                status_parts.append(f"⚠️ No data for {ticker}")
                continue

            prices_df = prices_df.sort_values("date", ascending=True)

            # Filter by base date if provided
            if base_date_str:
                prices_df = prices_df[prices_df["date"] >= base_date_str]
                if prices_df.empty:
                    status_parts.append(f"⚠️ No data for {ticker} from {base_date_str}")
                    continue

            prices_df["date"] = pd.to_datetime(prices_df["date"])

            color = colors[i % len(colors)]

            if show_usd and not usd_df.empty:
                # Merge with USD rates
                merged_df = pd.merge_asof(prices_df.sort_values("date"), usd_df.sort_values("date"), on="date", direction="backward")

                # Calculate USD price
                mask = merged_df["usd_try_rate"].notna() & (merged_df["usd_try_rate"] > 0)
                merged_df = merged_df[mask].copy()

                if merged_df.empty:
                    status_parts.append(f"⚠️ No USD rates available for {ticker}")
                    continue

                merged_df["price_usd"] = merged_df["price"] / merged_df["usd_try_rate"]

                # Normalize to 100
                first_price = merged_df["price_usd"].iloc[0]
                merged_df["normalized"] = (merged_df["price_usd"] / first_price) * 100

                fig.add_trace(
                    go.Scatter(
                        x=merged_df["date"],
                        y=merged_df["normalized"],
                        name=f"{ticker}",
                        line=dict(color=color, width=2),
                        hovertemplate=f"{ticker}<br>%{{x|%Y-%m-%d}}<br>Index: %{{y:.2f}}<br>USD: $%{{customdata:.6f}}<extra></extra>",
                        customdata=merged_df["price_usd"],
                    )
                )
                status_parts.append(f"✅ {ticker}: {len(merged_df)} points (USD)")
            else:
                # TRY only - normalize to 100
                first_price = prices_df["price"].iloc[0]
                prices_df["normalized"] = (prices_df["price"] / first_price) * 100

                fig.add_trace(
                    go.Scatter(
                        x=prices_df["date"],
                        y=prices_df["normalized"],
                        name=f"{ticker}",
                        line=dict(color=color, width=2),
                        hovertemplate=f"{ticker}<br>%{{x|%Y-%m-%d}}<br>Index: %{{y:.2f}}<br>TRY: %{{customdata:.4f}}<extra></extra>",
                        customdata=prices_df["price"],
                    )
                )
                status_parts.append(f"✅ {ticker}: {len(prices_df)} points (TRY)")

        # Add reference line at 100
        fig.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="Base (100)")

        currency = "USD" if show_usd else "TRY"
        base_info = f" from {base_date_str}" if base_date_str else ""
        fig.update_layout(
            title=dict(text=f"📊 Fund Comparison (Normalized to 100, {currency}){base_info}", font=dict(size=20)),
            xaxis_title="Date",
            yaxis_title=f"Normalized Value (100 = {base_date_str or 'Start'})",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            template="plotly_white",
            height=500,
        )

        return fig, "\n".join(status_parts)
