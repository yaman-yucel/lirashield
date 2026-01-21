"""
Turkish Real Return Tracker - Gradio UI

Track your portfolio returns adjusted for inflation using CPI/USD benchmarks.
Separate data entry for transactions and CPI/USD rates.
"""

from datetime import datetime

import gradio as gr
import pandas as pd

from database import (
    init_db,
    add_transaction,
    get_portfolio,
    delete_transaction,
    add_cpi_usd_rate,
    get_cpi_usd_rates,
    delete_cpi_usd_rate,
    bulk_import_cpi_usd_rates,
    add_cpi_official,
    get_cpi_official_data,
    delete_cpi_official,
    bulk_import_cpi_official,
    get_unique_tickers,
)
from analysis import calculate_real_return, fetch_usd_rate_from_yfinance, get_usd_rate

# Initialize database on startup
init_db()


# ============== TRANSACTION HANDLERS ==============


def handle_add_transaction(date: str, ticker: str, qty: float, price: float, notes: str):
    """Handle adding a new transaction."""
    if not ticker.strip():
        return "❌ Ticker is required", get_portfolio()
    if qty <= 0:
        return "❌ Quantity must be positive", get_portfolio()
    if price <= 0:
        return "❌ Price must be positive", get_portfolio()

    # DateTime with type="string" returns "YYYY-MM-DD HH:MM:SS", extract date part
    date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")

    result = add_transaction(date_str, ticker, qty, price, notes)
    return result, get_portfolio()


def handle_delete_transaction(transaction_id: int):
    """Handle deleting a transaction."""
    if transaction_id <= 0:
        return "❌ Enter a valid transaction ID", get_portfolio()
    result = delete_transaction(int(transaction_id))
    return result, get_portfolio()


def refresh_portfolio():
    """Refresh the portfolio table."""
    return get_portfolio()


# ============== CPI/USD RATE HANDLERS ==============


def handle_add_rate(date: str, rate: float, notes: str):
    """Handle adding a new CPI/USD rate."""
    if rate <= 0:
        return "❌ Rate must be positive", get_cpi_usd_rates()

    date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")
    result = add_cpi_usd_rate(date_str, rate, source="manual", notes=notes)
    return result, get_cpi_usd_rates()


def handle_delete_rate(rate_id: int):
    """Handle deleting a CPI/USD rate."""
    if rate_id <= 0:
        return "❌ Enter a valid rate ID", get_cpi_usd_rates()
    result = delete_cpi_usd_rate(int(rate_id))
    return result, get_cpi_usd_rates()


def handle_fetch_rate(date: str):
    """Fetch USD/TRY rate from yfinance and add to database."""
    date_str = str(date)[:10] if date else datetime.now().strftime("%Y-%m-%d")

    rate = fetch_usd_rate_from_yfinance(date_str)
    if rate:
        result = add_cpi_usd_rate(date_str, rate, source="yfinance", notes="Fetched automatically")
        return result, get_cpi_usd_rates()
    return f"❌ Could not fetch rate for {date_str}. Try a different date or enter manually.", get_cpi_usd_rates()


def handle_bulk_import(csv_text: str):
    """Handle bulk import of CPI/USD rates."""
    result = bulk_import_cpi_usd_rates(csv_text)
    return result, get_cpi_usd_rates()


def refresh_rates():
    """Refresh the rates table."""
    return get_cpi_usd_rates()


# ============== OFFICIAL CPI HANDLERS (TCMB) ==============


def handle_add_cpi(year_month: str, cpi_yoy: float, cpi_mom: float, notes: str):
    """Handle adding official CPI data."""
    if cpi_yoy <= 0:
        return "❌ YoY rate must be positive", get_cpi_official_data()
    result = add_cpi_official(year_month, cpi_yoy, cpi_mom if cpi_mom != 0 else None, notes)
    return result, get_cpi_official_data()


def handle_delete_cpi(cpi_id: int):
    """Handle deleting a CPI entry."""
    if cpi_id <= 0:
        return "❌ Enter a valid CPI ID", get_cpi_official_data()
    result = delete_cpi_official(int(cpi_id))
    return result, get_cpi_official_data()


def handle_bulk_import_cpi(csv_text: str):
    """Handle bulk import of CPI data."""
    result = bulk_import_cpi_official(csv_text)
    return result, get_cpi_official_data()


def refresh_cpi():
    """Refresh the CPI table."""
    return get_cpi_official_data()


# ============== ANALYSIS HANDLERS ==============


def analyze_portfolio(price_table_df: pd.DataFrame, auto_fetch: bool):
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

        analysis = calculate_real_return(buy_price, current_price, buy_date, auto_fetch_usd=auto_fetch)

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
                    "Nominal": f"{nominal:+.2f}%",
                    "USD Δ": f"{usd_inf:+.2f}%" if usd_inf is not None else "—",
                    "CPI Δ": f"{cpi_inf:+.2f}%" if cpi_inf is not None else "—",
                    "vs USD": usd_str,
                    "vs CPI": cpi_str,
                }
            )

    # Build summary table per ticker
    # First pass: calculate grand totals for percentage calculation
    grand_invested = sum(data["total_invested"] for data in ticker_summary.values())
    grand_current = sum(data["total_current"] for data in ticker_summary.values())

    summary_rows = []

    # Format real returns helper
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


# ============== GRADIO UI ==============


def create_ui() -> gr.Blocks:
    """Create the Gradio UI."""

    with gr.Blocks(title="Turkish Real Return Tracker") as demo:
        gr.Markdown(
            """
            # Turkish Real Return Tracker
            
            **Track your portfolio returns adjusted for inflation using USD/TRY as the benchmark.**
            
            *If USD rose 20% and your stock rose 20%, your real gain is 0%.*
            """,
        )

        # ============== TAB 1: TRANSACTIONS ==============
        with gr.Tab("📊 Transactions"):
            gr.Markdown("### Add Buy Transactions")

            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Row():
                        tx_date = gr.DateTime(label="Purchase Date", value=datetime.now(), type="string", include_time=False)
                        tx_ticker = gr.Textbox(label="Ticker / Fund Name", placeholder="e.g., TUPRS, THYAO, MAC", max_lines=1)
                    with gr.Row():
                        tx_qty = gr.Number(label="Quantity", value=1, minimum=0.0001, precision=4)
                        tx_price = gr.Number(label="Price Paid (TRY)", value=0.0, minimum=0, precision=4)
                    tx_notes = gr.Textbox(label="Notes (optional)", placeholder="e.g., Bought on dip", max_lines=1)

                    with gr.Row():
                        btn_add_tx = gr.Button("💾 Save Transaction", variant="primary")

                with gr.Column(scale=1):
                    gr.Markdown("### Delete Transaction")
                    del_tx_id = gr.Number(label="Transaction ID to Delete", value=0, minimum=0)
                    btn_del_tx = gr.Button("🗑️ Delete", variant="secondary")

            tx_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("### Your Transactions")
            tx_table = gr.Dataframe(
                value=get_portfolio(),
                label="Portfolio Transactions",
                interactive=False,
            )
            btn_refresh_tx = gr.Button("🔄 Refresh Table")

            # Transaction event handlers
            btn_add_tx.click(handle_add_transaction, inputs=[tx_date, tx_ticker, tx_qty, tx_price, tx_notes], outputs=[tx_status, tx_table])
            btn_del_tx.click(handle_delete_transaction, inputs=[del_tx_id], outputs=[tx_status, tx_table])
            btn_refresh_tx.click(refresh_portfolio, outputs=[tx_table])

        # ============== TAB 2: OFFICIAL CPI (TCMB) ==============
        with gr.Tab("📊 CPI (TCMB)"):
            gr.Markdown(
                """
                ### Official CPI Data from Turkish Central Bank (TCMB)
                
                Enter monthly CPI data from [TCMB Consumer Prices](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data/Consumer+Prices).
                
                **YoY** = Year-over-Year inflation rate (e.g., 44.38% for Dec 2024)  
                **MoM** = Month-over-Month change (e.g., 1.03% for Dec 2024)
                """
            )

            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("#### Add Monthly CPI")
                    with gr.Row():
                        cpi_month = gr.Textbox(label="Month (YYYY-MM)", value=datetime.now().strftime("%Y-%m"), max_lines=1)
                        cpi_yoy = gr.Number(label="YoY Rate (%)", value=0, minimum=0)
                        cpi_mom = gr.Number(label="MoM Rate (%)", value=0)
                    cpi_notes = gr.Textbox(label="Notes (optional)", max_lines=1)

                    with gr.Row():
                        btn_add_cpi = gr.Button("💾 Save CPI Data", variant="primary")

                with gr.Column(scale=1):
                    gr.Markdown("#### Delete Entry")
                    del_cpi_id = gr.Number(label="CPI ID to Delete", value=0, minimum=0)
                    btn_del_cpi = gr.Button("🗑️ Delete", variant="secondary")

            cpi_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("---")

            with gr.Accordion("📥 Bulk Import CPI Data (CSV)", open=False):
                gr.Markdown(
                    """
                    Paste CSV data from TCMB in format: `month,yoy,mom` (one per line)
                    
                    Supports both `MM-YYYY` and `YYYY-MM` formats.
                    
                    **Recent TCMB Data (copy & paste):**
                    ```
                    12-2024,44.38,1.03
                    11-2024,47.09,2.24
                    10-2024,48.58,2.88
                    09-2024,49.38,2.97
                    08-2024,51.97,2.47
                    07-2024,61.78,3.23
                    06-2024,71.60,1.64
                    05-2024,75.45,3.37
                    04-2024,69.80,3.18
                    03-2024,68.50,3.16
                    02-2024,67.07,4.53
                    01-2024,64.86,6.70
                    ```
                    """
                )
                bulk_cpi_csv = gr.Textbox(label="CSV Data", placeholder="12-2024,44.38,1.03\n11-2024,47.09,2.24", lines=5)
                btn_bulk_import_cpi = gr.Button("📥 Import All", variant="primary")

            gr.Markdown("### Stored CPI Data")
            cpi_table = gr.Dataframe(
                value=get_cpi_official_data(),
                label="Official CPI Data (TCMB)",
                interactive=False,
            )
            btn_refresh_cpi = gr.Button("🔄 Refresh Table")

            # CPI event handlers
            btn_add_cpi.click(handle_add_cpi, inputs=[cpi_month, cpi_yoy, cpi_mom, cpi_notes], outputs=[cpi_status, cpi_table])
            btn_del_cpi.click(handle_delete_cpi, inputs=[del_cpi_id], outputs=[cpi_status, cpi_table])
            btn_bulk_import_cpi.click(handle_bulk_import_cpi, inputs=[bulk_cpi_csv], outputs=[cpi_status, cpi_table])
            btn_refresh_cpi.click(refresh_cpi, outputs=[cpi_table])

        # ============== TAB 3: USD/TRY RATES ==============
        with gr.Tab("💵 USD Rates"):
            gr.Markdown(
                """
                ### USD/TRY Exchange Rates (Inflation Proxy)
                
                The "street method" uses USD/TRY exchange rate changes as an inflation proxy.
                You can enter rates manually or fetch them automatically from Yahoo Finance.
                """
            )

            with gr.Row():
                with gr.Column(scale=2):
                    gr.Markdown("#### Add Single Rate")
                    with gr.Row():
                        rate_date = gr.DateTime(label="Rate Date", value=datetime.now(), type="string", include_time=False)
                        rate_value = gr.Number(label="USD/TRY Rate", value=0, minimum=0, precision=4)
                    rate_notes = gr.Textbox(label="Notes (optional)", max_lines=1)

                    with gr.Row():
                        btn_add_rate = gr.Button("💾 Save Rate", variant="primary")
                        btn_fetch_rate = gr.Button("🌐 Fetch from Yahoo Finance", variant="secondary")

                with gr.Column(scale=1):
                    gr.Markdown("#### Delete Rate")
                    del_rate_id = gr.Number(label="Rate ID to Delete", value=0, minimum=0)
                    btn_del_rate = gr.Button("🗑️ Delete", variant="secondary")

            rate_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("---")

            with gr.Accordion("📥 Bulk Import Rates (CSV)", open=False):
                gr.Markdown(
                    """
                    Paste CSV data in format: `date,rate` (one per line)
                    
                    Example:
                    ```
                    2024-01-01,29.5
                    2024-02-01,30.2
                    2024-03-01,32.1
                    ```
                    """
                )
                bulk_csv = gr.Textbox(label="CSV Data", placeholder="2024-01-01,29.5\n2024-02-01,30.2", lines=5)
                btn_bulk_import = gr.Button("📥 Import All", variant="primary")

            gr.Markdown("### Stored Rates")
            rate_table = gr.Dataframe(
                value=get_cpi_usd_rates(),
                label="USD/TRY Rates",
                interactive=False,
            )
            btn_refresh_rates = gr.Button("🔄 Refresh Table")

            # Rate event handlers
            btn_add_rate.click(handle_add_rate, inputs=[rate_date, rate_value, rate_notes], outputs=[rate_status, rate_table])
            btn_fetch_rate.click(handle_fetch_rate, inputs=[rate_date], outputs=[rate_status, rate_table])
            btn_del_rate.click(handle_delete_rate, inputs=[del_rate_id], outputs=[rate_status, rate_table])
            btn_bulk_import.click(handle_bulk_import, inputs=[bulk_csv], outputs=[rate_status, rate_table])
            btn_refresh_rates.click(refresh_rates, outputs=[rate_table])

        # ============== TAB 4: ANALYSIS ==============
        with gr.Tab("📈 Analyze Returns"):
            gr.Markdown(
                """
                ### Calculate Real Returns
                
                Enter current prices for your assets to see inflation-adjusted gains.
                
                **Formula:** Real Return = ((1 + Nominal Return) / (1 + Inflation)) - 1
                """
            )

            gr.Markdown("#### Current Prices")

            def get_ticker_price_table():
                """Generate a table with tickers for price entry."""
                tickers = get_unique_tickers()
                if not tickers:
                    return pd.DataFrame({"Ticker": ["No tickers"], "Current Price": [0.0]})
                return pd.DataFrame({"Ticker": tickers, "Current Price": [0.0] * len(tickers)})

            with gr.Row():
                price_table = gr.Dataframe(
                    value=get_ticker_price_table(),
                    label="Enter current prices for each ticker",
                    interactive=True,
                    column_count=(2, "fixed"),
                    scale=2,
                )
                with gr.Column(scale=1):
                    btn_refresh_tickers = gr.Button("🔄 Refresh Tickers", variant="secondary")
                    auto_fetch_chk = gr.Checkbox(label="Auto-fetch missing USD rates", value=True, info="Fetches from Yahoo Finance")

            btn_calc = gr.Button("🧮 Calculate Real Gains", variant="primary", size="lg")

            btn_refresh_tickers.click(lambda: get_ticker_price_table(), outputs=[price_table])

            calc_status = gr.Textbox(label="Calculation Status", interactive=False)

            gr.Markdown("#### Portfolio Summary")
            summary_table = gr.Dataframe(
                label="Summary by Ticker",
                interactive=False,
            )

            gr.Markdown("#### Transaction Details")
            out_table = gr.Dataframe(
                label="Individual Transactions",
                interactive=False,
            )

            gr.Markdown(
                """
                ---
                **Legend:**
                - 🟢 Positive real return (beat inflation)
                - 🔴 Negative real return (inflation won)
                - **P/L** = Profit/Loss (nominal, in TRY)
                - **Real (USD)** = Weighted average real return vs USD
                - **Real (CPI)** = Weighted average real return vs official CPI
                """
            )

            # Analysis event handlers
            btn_calc.click(analyze_portfolio, inputs=[price_table, auto_fetch_chk], outputs=[out_table, summary_table, calc_status])

        # ============== TAB 5: HELP ==============
        with gr.Tab("❓ Help"):
            gr.Markdown(
                """
                ## How to Use This App
                
                ### Step 1: Add Your Transactions
                1. Go to the **📊 Transactions** tab
                2. Enter the date you bought, ticker symbol, quantity, and price
                3. Click "Save Transaction"
                
                ### Step 2: Add USD/TRY Rates
                1. Go to the **💵 USD Rates** tab
                2. Add the USD/TRY rate for your buy date(s)
                3. Add today's USD/TRY rate
                4. You can fetch rates automatically from Yahoo Finance
                
                ### Step 3: Analyze
                1. Go to the **📈 Analyze Returns** tab
                2. Enter current prices in the table (one row per ticker)
                3. Click "Calculate Real Gains"
                
                ---
                
                ## Understanding Real Returns
                
                **Nominal Return:** How much your investment went up/down in TRY terms.
                
                **USD Change:** How much TRY lost value against USD.
                
                **Real Return:** Your actual purchasing power gain/loss.
                
                ### Example
                
                - You bought TUPRS at 100 TRY when USD was 30 TRY
                - Now TUPRS is 150 TRY and USD is 36 TRY
                - Nominal gain: +50%
                - USD change: +20% (TRY lost 20% against USD)
                - Real return: (1.50 / 1.20) - 1 = **+25%**
                
                ---
                
                ## Data Sources
                
                - **CPI**: [TCMB Consumer Prices](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data/Consumer+Prices)
                - **USD/TRY**: Yahoo Finance (TRY=X ticker)
                
                The app stores all data in a local SQLite database (`portfolio.db`).
                """
            )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch()
