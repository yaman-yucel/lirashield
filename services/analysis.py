"""
Analysis service for calculating real returns.
"""

from datetime import datetime

import pandas as pd

from core.database import get_portfolio, get_unique_tickers, get_all_fund_latest_prices
from core.analysis import calculate_real_return, get_usd_rate


class AnalysisService:
    """Service for portfolio analysis and real return calculations."""

    @staticmethod
    def analyze_portfolio(price_table_df: pd.DataFrame | None, auto_fetch: bool) -> tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        Analyze portfolio with current prices and calculate real returns.

        Args:
            price_table_df: DataFrame with Ticker and Current Price columns
            auto_fetch: Whether to auto-fetch missing USD rates from yfinance

        Returns:
            Tuple of (details_table, summary_table, status_message)
        """
        df = get_portfolio()
        if df.empty:
            empty_msg = pd.DataFrame({"Message": ["No transactions found. Add some in the Transactions tab."]})
            return empty_msg, empty_msg, ""

        # Parse current prices from the table
        price_map: dict[str, float] = {}
        if price_table_df is not None and not price_table_df.empty:
            for _, row in price_table_df.iterrows():
                ticker = str(row.get("Ticker", "")).strip().upper()
                price = row.get("Current Price", 0)
                if ticker and price and float(price) > 0:
                    price_map[ticker] = float(price)

        results = []
        errors = []

        # Track per-ticker summary data
        ticker_summary: dict[str, dict] = {}

        for _, row in df.iterrows():
            ticker = row["ticker"]
            buy_price = row["price_per_share"]
            buy_date = row["date"]
            quantity = row["quantity"]
            # Handle None/NaN
            tax_rate_raw = row.get("tax_rate", 0)
            tax_rate = 0.0 if pd.isna(tax_rate_raw) else float(tax_rate_raw)
            invested = buy_price * quantity

            # Get current price (default to buy price if not provided)
            current_price = price_map.get(ticker.upper(), buy_price)
            current_value = current_price * quantity

            # Initialize ticker summary if needed
            if ticker not in ticker_summary:
                ticker_summary[ticker] = {
                    "total_qty": 0,
                    "total_invested": 0,
                    "total_current": 0,
                    "current_price": current_price,
                    "weighted_real_usd": [],
                    "weighted_real_cpi": [],
                }

            ticker_summary[ticker]["total_qty"] += quantity
            ticker_summary[ticker]["total_invested"] += invested
            ticker_summary[ticker]["total_current"] += current_value

            analysis = calculate_real_return(buy_price, current_price, buy_date, auto_fetch_usd=auto_fetch, tax_rate=tax_rate)

            tax_str = f"{tax_rate:.2f}%" if tax_rate > 0 else "0%"

            if "error" in analysis:
                errors.append(f"• {ticker} ({buy_date}): {analysis['error']}")
                results.append(
                    {
                        "ID": row["id"],
                        "Date": buy_date,
                        "Ticker": ticker,
                        "Qty": quantity,
                        "Buy": f"{buy_price:.4f}",
                        "Now": f"{current_price:.4f}",
                        "Tax": tax_str,
                        "Nominal": "—",
                        "USD Δ": "—",
                        "CPI Δ": "—",
                        "vs USD": "⚠️ N/A",
                        "vs CPI": "⚠️ N/A",
                    }
                )
            else:
                nominal = analysis["nominal_pct"]
                usd_inf = analysis["usd_inflation_pct"]
                cpi_inf = analysis["cpi_inflation_pct"]
                real_usd = analysis["real_return_usd_pct"]
                real_cpi = analysis["real_return_cpi_pct"]

                # Track weighted real returns for summary
                if real_usd is not None:
                    ticker_summary[ticker]["weighted_real_usd"].append((invested, real_usd))
                if real_cpi is not None:
                    ticker_summary[ticker]["weighted_real_cpi"].append((invested, real_cpi))

                # Format USD-based real gain
                if real_usd is not None:
                    usd_str = f"{real_usd:+.2f}%"
                    if real_usd > 0:
                        usd_str = f"🟢 {usd_str}"
                    elif real_usd < 0:
                        usd_str = f"🔴 {usd_str}"
                    else:
                        usd_str = f"⚪ {usd_str}"
                else:
                    usd_str = "—"

                # Format CPI-based real gain
                if real_cpi is not None:
                    cpi_str = f"{real_cpi:+.2f}%"
                    if real_cpi > 0:
                        cpi_str = f"🟢 {cpi_str}"
                    elif real_cpi < 0:
                        cpi_str = f"🔴 {cpi_str}"
                    else:
                        cpi_str = f"⚪ {cpi_str}"
                else:
                    cpi_str = "—"

                results.append(
                    {
                        "ID": row["id"],
                        "Date": buy_date,
                        "Ticker": ticker,
                        "Qty": quantity,
                        "Buy": f"{buy_price:.4f}",
                        "Now": f"{current_price:.4f}",
                        "Tax": tax_str,
                        "Nominal": f"{nominal:+.2f}%",
                        "USD Δ": f"{usd_inf:+.2f}%" if usd_inf is not None else "—",
                        "CPI Δ": f"{cpi_inf:+.2f}%" if cpi_inf is not None else "—",
                        "vs USD": usd_str,
                        "vs CPI": cpi_str,
                    }
                )

        # Build summary table per ticker
        grand_invested = sum(data["total_invested"] for data in ticker_summary.values())
        grand_current = sum(data["total_current"] for data in ticker_summary.values())

        summary_rows = []

        def fmt_real(val):
            if val is None:
                return "—"
            s = f"{val:+.2f}%"
            if val > 0:
                return f"🟢 {s}"
            elif val < 0:
                return f"🔴 {s}"
            return f"⚪ {s}"

        for ticker, data in sorted(ticker_summary.items()):
            invested = data["total_invested"]
            current = data["total_current"]

            nominal_pct = ((current - invested) / invested * 100) if invested > 0 else 0
            nominal_gain = current - invested

            # Calculate allocation percentages
            alloc_invested = (invested / grand_invested * 100) if grand_invested > 0 else 0
            alloc_current = (current / grand_current * 100) if grand_current > 0 else 0

            # Calculate weighted average real returns
            avg_real_usd = None
            if data["weighted_real_usd"]:
                total_weight = sum(w for w, _ in data["weighted_real_usd"])
                if total_weight > 0:
                    avg_real_usd = sum(w * r for w, r in data["weighted_real_usd"]) / total_weight

            avg_real_cpi = None
            if data["weighted_real_cpi"]:
                total_weight = sum(w for w, _ in data["weighted_real_cpi"])
                if total_weight > 0:
                    avg_real_cpi = sum(w * r for w, r in data["weighted_real_cpi"]) / total_weight

            summary_rows.append(
                {
                    "Ticker": ticker,
                    "Shares": f"{data['total_qty']:.2f}",
                    "Avg Cost": f"{invested / data['total_qty']:.4f}" if data["total_qty"] > 0 else "—",
                    "Price": f"{data['current_price']:.4f}",
                    "Invested": f"{invested:,.0f}",
                    "% Inv": f"{alloc_invested:.1f}%",
                    "Value": f"{current:,.0f}",
                    "% Val": f"{alloc_current:.1f}%",
                    "P/L": f"{nominal_gain:+,.0f}",
                    "P/L %": f"{nominal_pct:+.2f}%",
                    "Real (USD)": fmt_real(avg_real_usd),
                    "Real (CPI)": fmt_real(avg_real_cpi),
                }
            )

        # Add grand total row
        if summary_rows:
            grand_nominal_pct = ((grand_current - grand_invested) / grand_invested * 100) if grand_invested > 0 else 0
            grand_pl = grand_current - grand_invested
            summary_rows.append(
                {
                    "Ticker": "📊 TOTAL",
                    "Shares": "",
                    "Avg Cost": "",
                    "Price": "",
                    "Invested": f"{grand_invested:,.0f}",
                    "% Inv": "100%",
                    "Value": f"{grand_current:,.0f}",
                    "% Val": "100%",
                    "P/L": f"{grand_pl:+,.0f}",
                    "P/L %": f"{grand_nominal_pct:+.2f}%",
                    "Real (USD)": "",
                    "Real (CPI)": "",
                }
            )

        # Get today's USD rate for display
        today = datetime.now().strftime("%Y-%m-%d")
        today_usd = get_usd_rate(today, auto_fetch=auto_fetch)

        # Build status message
        status_parts = []
        if today_usd:
            status_parts.append(f"📊 Today's USD/TRY: {today_usd:.4f}")
        if errors:
            status_parts.append("\n".join(errors))
        else:
            status_parts.append("✅ All calculations successful")

        return pd.DataFrame(results), pd.DataFrame(summary_rows), "\n".join(status_parts)
