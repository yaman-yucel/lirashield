"""
Analysis service for calculating real returns.

Uses FIFO (First In, First Out) cost basis for:
- Matching sell transactions to buy transactions
- Calculating realized gains on closed positions
- Calculating unrealized gains on open positions
"""

from datetime import datetime

import pandas as pd

from core.database import (
    ASSET_CASH,
    CURRENCY_USD,
)
from core.analysis import calculate_real_return, get_usd_rate
from services.fifo import calculate_fifo_all_tickers


class AnalysisService:
    """Service for portfolio analysis and real return calculations using FIFO cost basis."""

    @staticmethod
    def analyze_portfolio(price_table_df: pd.DataFrame | None, auto_fetch: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, str]:
        """
        Analyze portfolio with current prices and calculate real returns using FIFO.

        Uses FIFO (First In, First Out) to:
        - Match sell transactions to buy transactions chronologically
        - Calculate realized gains from closed positions
        - Calculate unrealized gains from open positions

        Args:
            price_table_df: DataFrame with Ticker and Current Price columns
            auto_fetch: Whether to auto-fetch missing USD rates from yfinance (default: False)

        Returns:
            Tuple of (details_table, summary_table, status_message)
        """
        # Get FIFO results for all tickers
        fifo_results = calculate_fifo_all_tickers()

        if not fifo_results:
            empty_msg = pd.DataFrame({"Message": ["No transactions found. Add some in the Transactions tab."]})
            return empty_msg, empty_msg, ""

        # Parse current prices from the table (with currency info)
        price_map: dict[str, float] = {}
        currency_map: dict[str, str] = {}
        if price_table_df is not None and not price_table_df.empty:
            for _, row in price_table_df.iterrows():
                ticker = str(row.get("Ticker", "")).strip().upper()
                price = row.get("Current Price", 0)
                currency = str(row.get("Currency", "TRY")).strip().upper()
                if ticker and price and float(price) > 0:
                    price_map[ticker] = float(price)
                    currency_map[ticker] = currency if currency in ["TRY", "USD"] else "TRY"

        results = []
        errors = []
        ticker_summary: dict[str, dict] = {}
        today = datetime.now().strftime("%Y-%m-%d")

        # Process each ticker's FIFO results
        for ticker, fifo in fifo_results.items():
            currency = fifo.currency
            asset_type = fifo.asset_type

            # Get current price for this ticker
            current_price = price_map.get(ticker.upper(), 0)

            # Initialize ticker summary
            ticker_summary[ticker] = {
                "shares_held": fifo.total_shares_held,
                "cost_basis": fifo.total_cost_basis,
                "avg_cost": fifo.avg_cost_per_share,
                "current_price": current_price,
                "current_value": fifo.total_shares_held * current_price if current_price > 0 else 0,
                "realized_gain": fifo.total_realized_gain,
                "currency": currency,
                "asset_type": asset_type,
                "weighted_real_usd": [],
                "weighted_real_cpi": [],
            }

            # Process open lots (unrealized positions)
            for lot in fifo.open_lots:
                buy_price = lot.buy_price
                buy_date = lot.buy_date
                quantity = lot.remaining_quantity
                tax_rate = lot.tax_rate

                # For cash, price is always 1
                if asset_type == ASSET_CASH:
                    buy_price = 1.0
                    lot_current_price = 1.0
                else:
                    lot_current_price = current_price if current_price > 0 else buy_price

                invested = buy_price * quantity
                current_value = lot_current_price * quantity

                # Calculate nominal return in original currency first (before conversion)
                # This ensures nominal return reflects actual asset performance, not exchange rate changes
                if asset_type == ASSET_CASH:
                    analysis = {
                        "nominal_pct": 0.0,
                        "usd_inflation_pct": None,
                        "real_return_usd_pct": None,
                        "cpi_inflation_pct": None,
                        "real_return_cpi_pct": None,
                    }
                else:
                    # Calculate nominal return in original currency (USD or TRY)
                    # Tax is applied on gains in the original currency
                    try_gain = max(0, lot_current_price - buy_price)
                    tax_amount = try_gain * (tax_rate / 100)
                    after_tax_current = lot_current_price - tax_amount
                    nominal_return = (after_tax_current - buy_price) / buy_price
                    nominal_pct = round(nominal_return * 100, 2)

                    # For USD stocks, convert to TRY for real return calculations
                    # (comparing against TRY inflation benchmarks)
                    buy_usd_rate = get_usd_rate(buy_date, auto_fetch=auto_fetch) if currency == CURRENCY_USD else None
                    current_usd_rate = get_usd_rate(today, auto_fetch=auto_fetch) if currency == CURRENCY_USD else None

                    if currency == CURRENCY_USD and buy_usd_rate and current_usd_rate:
                        # Convert USD prices to TRY for real return calculation
                        buy_price_try = buy_price * buy_usd_rate
                        current_price_try = lot_current_price * current_usd_rate
                        # Calculate real return using TRY prices (for comparison with TRY inflation)
                        # Use tax_rate=0 since tax was already applied in USD calculation above
                        # Skip USD and CPI calculations for USD stocks (CPI is Turkish inflation measure)
                        analysis = calculate_real_return(buy_price_try, current_price_try, buy_date, auto_fetch_usd=auto_fetch, tax_rate=0, skip_usd_cpi=True)
                        # Override nominal_pct with the USD-based calculation (original currency)
                        analysis["nominal_pct"] = nominal_pct
                    else:
                        # TRY assets - use standard calculation
                        analysis = calculate_real_return(buy_price, lot_current_price, buy_date, auto_fetch_usd=auto_fetch, tax_rate=tax_rate, skip_usd_cpi=False)

                tax_str = f"{tax_rate:.2f}%" if tax_rate > 0 else "0%"
                currency_display = currency if currency else "TRY"

                if "error" in analysis:
                    errors.append(f"• {ticker} ({buy_date}): {analysis['error']}")
                    results.append(
                        {
                            "Type": "📈 OPEN",
                            "Date": buy_date,
                            "Ticker": ticker,
                            "Qty": f"{quantity:.4f}",
                            "Buy": f"{buy_price:.4f} {currency_display}",
                            "Now": f"{lot_current_price:.4f} {currency_display}",
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

                    # Track weighted real returns
                    if real_usd is not None:
                        ticker_summary[ticker]["weighted_real_usd"].append((invested, real_usd))
                    if real_cpi is not None:
                        ticker_summary[ticker]["weighted_real_cpi"].append((invested, real_cpi))

                    # Format real returns
                    usd_str = AnalysisService._format_real_return(real_usd)
                    cpi_str = AnalysisService._format_real_return(real_cpi)

                    results.append(
                        {
                            "Type": "📈 OPEN",
                            "Date": buy_date,
                            "Ticker": ticker,
                            "Qty": f"{quantity:.4f}",
                            "Buy": f"{buy_price:.4f} {currency_display}",
                            "Now": f"{lot_current_price:.4f} {currency_display}",
                            "Tax": tax_str,
                            "Nominal": f"{nominal:+.2f}%",
                            "USD Δ": f"{usd_inf:+.2f}%" if usd_inf is not None else "—",
                            "CPI Δ": f"{cpi_inf:+.2f}%" if cpi_inf is not None else "—",
                            "vs USD": usd_str,
                            "vs CPI": cpi_str,
                        }
                    )

            # Process closed lots (realized positions)
            for lot in fifo.closed_lots:
                realized_gain = lot.realized_gain
                realized_pct = lot.realized_gain_pct
                currency_display = currency if currency else "TRY"

                results.append(
                    {
                        "Type": "✅ SOLD",
                        "Date": f"{lot.buy_date} → {lot.sell_date}",
                        "Ticker": ticker,
                        "Qty": f"{lot.quantity:.4f}",
                        "Buy": f"{lot.buy_price:.4f} {currency_display}",
                        "Now": f"{lot.sell_price:.4f} {currency_display}",
                        "Tax": f"{lot.tax_rate:.2f}%",
                        "Nominal": f"{realized_pct:+.2f}%",
                        "USD Δ": f"({lot.holding_days}d)",
                        "CPI Δ": "—",
                        "vs USD": f"{realized_gain:+,.0f}",
                        "vs CPI": "—",
                    }
                )

        # Get today's USD rate for conversions
        today_usd = get_usd_rate(today, auto_fetch=auto_fetch)

        # Build summary table
        summary_rows = []
        # Track totals in both currencies
        grand_cost_basis_try = 0
        grand_current_value_try = 0
        grand_realized_try = 0
        grand_cost_basis_usd = 0
        grand_current_value_usd = 0
        grand_realized_usd = 0

        for ticker, data in sorted(ticker_summary.items()):
            shares = data["shares_held"]
            cost_basis = data["cost_basis"]
            current_value = data["current_value"]
            realized = data["realized_gain"]
            avg_cost = data["avg_cost"]
            current_price = data["current_price"]
            currency = data["currency"]

            # Convert to both currencies for totals
            if currency == CURRENCY_USD:
                # USD asset - convert to TRY for TRY totals
                if today_usd:
                    cost_basis_try = cost_basis * today_usd
                    current_value_try = current_value * today_usd
                    realized_try = realized * today_usd
                else:
                    cost_basis_try = 0
                    current_value_try = 0
                    realized_try = 0
                # USD totals (original currency)
                cost_basis_usd = cost_basis
                current_value_usd = current_value
                realized_usd = realized
            else:
                # TRY asset - convert to USD for USD totals
                if today_usd:
                    cost_basis_usd = cost_basis / today_usd
                    current_value_usd = current_value / today_usd
                    realized_usd = realized / today_usd
                else:
                    cost_basis_usd = 0
                    current_value_usd = 0
                    realized_usd = 0
                # TRY totals (original currency)
                cost_basis_try = cost_basis
                current_value_try = current_value
                realized_try = realized

            # Add to grand totals
            grand_cost_basis_try += cost_basis_try
            grand_current_value_try += current_value_try
            grand_realized_try += realized_try
            grand_cost_basis_usd += cost_basis_usd
            grand_current_value_usd += current_value_usd
            grand_realized_usd += realized_usd

            # Unrealized P/L
            unrealized_pl = current_value - cost_basis if shares > 0 else 0
            unrealized_pct = (unrealized_pl / cost_basis * 100) if cost_basis > 0 else 0

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

            # Allocation percentages (calculated after loop)
            summary_rows.append(
                {
                    "Ticker": ticker,
                    "Shares": f"{shares:.4f}" if shares > 0 else "0 (sold)",
                    "Avg Cost": f"{avg_cost:.4f}" if avg_cost > 0 else "—",
                    "Price": f"{current_price:.4f}" if current_price > 0 else "—",
                    "Cost Basis": f"{cost_basis:,.0f}",
                    "Value": f"{current_value:,.0f}" if shares > 0 else "—",
                    "Unreal P/L": f"{unrealized_pl:+,.0f}" if shares > 0 else "—",
                    "Unreal %": f"{unrealized_pct:+.2f}%" if shares > 0 else "—",
                    "Realized": f"{realized:+,.0f}" if realized != 0 else "—",
                    "Real (USD)": AnalysisService._format_real_return(avg_real_usd),
                    "Real (CPI)": AnalysisService._format_real_return(avg_real_cpi),
                    "_currency": currency,
                }
            )

        # Add grand total rows - separate rows for TRY and USD
        if summary_rows:
            grand_unrealized_try = grand_current_value_try - grand_cost_basis_try
            grand_unrealized_pct_try = (grand_unrealized_try / grand_cost_basis_try * 100) if grand_cost_basis_try > 0 else 0
            total_gain_try = grand_unrealized_try + grand_realized_try

            # Add TRY total row
            summary_rows.append(
                {
                    "Ticker": "📊 TOTAL TRY",
                    "Shares": "",
                    "Avg Cost": "",
                    "Price": "",
                    "Cost Basis": f"{grand_cost_basis_try:,.0f}",
                    "Value": f"{grand_current_value_try:,.0f}",
                    "Unreal P/L": f"{grand_unrealized_try:+,.0f}",
                    "Unreal %": f"{grand_unrealized_pct_try:+.2f}%",
                    "Realized": f"{grand_realized_try:+,.0f}",
                    "Real (USD)": "",
                    "Real (CPI)": f"Total: {total_gain_try:+,.0f}",
                    "_currency": "",
                }
            )

            # Add USD total row if USD rate is available
            if today_usd:
                grand_unrealized_usd = grand_current_value_usd - grand_cost_basis_usd
                grand_unrealized_pct_usd = (grand_unrealized_usd / grand_cost_basis_usd * 100) if grand_cost_basis_usd > 0 else 0
                total_gain_usd = grand_unrealized_usd + grand_realized_usd

                summary_rows.append(
                    {
                        "Ticker": "📊 TOTAL USD",
                        "Shares": "",
                        "Avg Cost": "",
                        "Price": "",
                        "Cost Basis": f"{grand_cost_basis_usd:,.0f}",
                        "Value": f"{grand_current_value_usd:,.0f}",
                        "Unreal P/L": f"{grand_unrealized_usd:+,.0f}",
                        "Unreal %": f"{grand_unrealized_pct_usd:+.2f}%",
                        "Realized": f"{grand_realized_usd:+,.0f}",
                        "Real (USD)": "",
                        "Real (CPI)": f"Total: {total_gain_usd:+,.0f}",
                        "_currency": "",
                    }
                )

        # Build status message
        status_parts = []
        if today_usd:
            status_parts.append(f"📊 Today's USD/TRY: {today_usd:.4f}")
        status_parts.append("📈 Using FIFO cost basis method")
        if grand_realized_try != 0 or grand_realized_usd != 0:
            if today_usd:
                status_parts.append(f"💰 Total Realized Gains: {grand_realized_try:+,.0f} TRY / {grand_realized_usd:+,.0f} USD")
            else:
                status_parts.append(f"💰 Total Realized Gains: {grand_realized_try:+,.0f} TRY")
        if errors:
            status_parts.append("\n".join(errors))
        else:
            status_parts.append("✅ All calculations successful")

        # Remove internal columns before returning
        summary_df = pd.DataFrame(summary_rows)
        if "_currency" in summary_df.columns:
            summary_df = summary_df.drop(columns=["_currency"])

        return pd.DataFrame(results), summary_df, "\n".join(status_parts)

    @staticmethod
    def _format_real_return(val: float | None) -> str:
        """Format a real return value with color indicator."""
        if val is None:
            return "—"
        s = f"{val:+.2f}%"
        if val > 0:
            return f"🟢 {s}"
        elif val < 0:
            return f"🔴 {s}"
        return f"⚪ {s}"
