"""
LiraShield - Gradio UI

Track your portfolio returns adjusted for inflation using CPI/USD benchmarks.
Protect your purchasing power with real return analytics.
"""

from datetime import datetime

import gradio as gr

from core.database import init_db, get_unique_tickers, get_cpi_usd_rates, get_cpi_official_data
from ui.handlers import (
    # Transaction handlers
    handle_add_transaction,
    handle_delete_transaction,
    refresh_portfolio,
    handle_refresh_tefas_prices,
    get_ticker_price_table,
    # Rate handlers
    handle_add_rate,
    handle_delete_rate,
    handle_fetch_rate,
    handle_bulk_import,
    handle_refresh_all_usd_rates,
    handle_quick_refresh_usd_rates,
    handle_add_cpi,
    handle_delete_cpi,
    handle_bulk_import_cpi,
    refresh_cpi,
    # Chart handlers
    generate_fund_chart,
    generate_normalized_chart,
    # Analysis handlers
    analyze_portfolio,
)

# Initialize database on startup
init_db()


def create_ui() -> gr.Blocks:
    """Create the Gradio UI."""

    with gr.Blocks(title="LiraShield") as demo:
        gr.Markdown(
            """
            # LiraShield
            
            **Track your portfolio returns adjusted for inflation using USD/TRY as the benchmark.**
            
            *If USD rose 20% and your stock rose 20%, your real gain is 0%.*
            """,
        )

        # ============== TAB 1: TRANSACTIONS ==============
        with gr.Tab("📊 Transactions"):
            gr.Markdown(
                """
                ### Add Buy Transactions
                *Price is automatically fetched from TEFAS based on the transaction date.*
                """
            )

            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Row():
                        tx_date = gr.DateTime(label="Purchase Date", value=datetime.now(), type="string", include_time=False)
                        tx_ticker = gr.Textbox(label="TEFAS Fund Code", placeholder="e.g., MAC, TI2, AFT", max_lines=1)
                    with gr.Row():
                        tx_qty = gr.Number(label="Quantity", value=1, minimum=0.0001, precision=4)
                        tx_tax = gr.Number(label="Tax Rate at Sell (%)", value=0, minimum=0, maximum=100, precision=2, info="Tax on TRY gains")
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
                value=refresh_portfolio(),
                label="Portfolio Transactions (prices from TEFAS)",
                interactive=False,
            )
            btn_refresh_tx = gr.Button("🔄 Refresh Table")

            # Transaction event handlers
            btn_add_tx.click(handle_add_transaction, inputs=[tx_date, tx_ticker, tx_qty, tx_tax, tx_notes], outputs=[tx_status, tx_table])
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
                Click the button below to fetch all historical rates needed for your portfolio.
                """
            )

            with gr.Row():
                with gr.Column(scale=2):
                    btn_quick_refresh_usd = gr.Button(
                        "⚡ Quick Refresh",
                        variant="primary",
                        size="lg",
                    )
                    gr.Markdown(
                        "*Fetches only missing rates (from latest stored date to today). Fast!*",
                    )
                with gr.Column(scale=2):
                    btn_refresh_all_usd = gr.Button(
                        "🔄 Full Refresh",
                        variant="secondary",
                        size="lg",
                    )
                    gr.Markdown(
                        "*Fetches all rates from earliest transaction to today. Use if gaps exist.*",
                    )
                with gr.Column(scale=1):
                    gr.Markdown("#### Delete Rate")
                    del_rate_id = gr.Number(label="Rate ID", value=0, minimum=0)
                    btn_del_rate = gr.Button("🗑️ Delete", variant="secondary")

            rate_status = gr.Textbox(label="Status", interactive=False, lines=4)

            gr.Markdown("### Stored USD/TRY Rates")
            rate_table = gr.Dataframe(
                value=get_cpi_usd_rates(),
                label="USD/TRY Rates (from Yahoo Finance)",
                interactive=False,
            )

            with gr.Accordion("📥 Manual Entry (Advanced)", open=False):
                gr.Markdown("*Use this only if you need to add rates manually for dates not covered by Yahoo Finance.*")
                with gr.Row():
                    rate_date = gr.DateTime(label="Rate Date", value=datetime.now(), type="string", include_time=False)
                    rate_value = gr.Number(label="USD/TRY Rate", value=0, minimum=0, precision=4)
                rate_notes = gr.Textbox(label="Notes (optional)", max_lines=1)
                with gr.Row():
                    btn_add_rate = gr.Button("💾 Save Rate", variant="secondary")
                    btn_fetch_rate = gr.Button("🌐 Fetch Single Date", variant="secondary")

            with gr.Accordion("📥 Bulk Import (CSV)", open=False):
                gr.Markdown(
                    """
                    Paste CSV data in format: `date,rate` (one per line)
                    
                    Example:
                    ```
                    2024-01-01,29.5
                    2024-02-01,30.2
                    ```
                    """
                )
                bulk_csv = gr.Textbox(label="CSV Data", placeholder="2024-01-01,29.5\n2024-02-01,30.2", lines=3)
                btn_bulk_import = gr.Button("📥 Import", variant="secondary")

            # Rate event handlers
            btn_quick_refresh_usd.click(handle_quick_refresh_usd_rates, outputs=[rate_status, rate_table])
            btn_refresh_all_usd.click(handle_refresh_all_usd_rates, outputs=[rate_status, rate_table])
            btn_add_rate.click(handle_add_rate, inputs=[rate_date, rate_value, rate_notes], outputs=[rate_status, rate_table])
            btn_fetch_rate.click(handle_fetch_rate, inputs=[rate_date], outputs=[rate_status, rate_table])
            btn_del_rate.click(handle_delete_rate, inputs=[del_rate_id], outputs=[rate_status, rate_table])
            btn_bulk_import.click(handle_bulk_import, inputs=[bulk_csv], outputs=[rate_status, rate_table])

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

            with gr.Row():
                price_table = gr.Dataframe(
                    value=get_ticker_price_table(),
                    label="Enter current prices for each ticker (auto-filled from TEFAS)",
                    interactive=True,
                    column_count=(2, "fixed"),
                    scale=2,
                )
                with gr.Column(scale=1):
                    btn_refresh_tickers = gr.Button("🔄 Refresh Tickers", variant="secondary")
                    btn_refresh_tefas = gr.Button("📈 Update TEFAS Prices", variant="secondary")
                    auto_fetch_chk = gr.Checkbox(label="Auto-fetch missing USD rates", value=True, info="Fetches from Yahoo Finance")

            tefas_status = gr.Textbox(label="TEFAS Update Status", interactive=False, visible=True)
            btn_calc = gr.Button("🧮 Calculate Real Gains", variant="primary", size="lg")

            btn_refresh_tickers.click(get_ticker_price_table, outputs=[price_table])
            btn_refresh_tefas.click(handle_refresh_tefas_prices, outputs=[tefas_status, price_table])

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
                - **Tax** = Tax rate on TRY gains at sell
                - **Nominal** = After-tax nominal return
                - **P/L** = Profit/Loss (nominal, in TRY)
                - **Real (USD)** = Weighted average real return vs USD (after tax)
                - **Real (CPI)** = Weighted average real return vs official CPI (after tax)
                """
            )

            # Analysis event handlers
            btn_calc.click(analyze_portfolio, inputs=[price_table, auto_fetch_chk], outputs=[out_table, summary_table, calc_status])

        # ============== TAB 5: FUND CHARTS ==============
        with gr.Tab("📉 Fund Charts"):
            gr.Markdown(
                """
                ### View Fund Price History
                
                View fund prices in both **TRY** and **USD** terms to understand real performance.
                
                *USD conversion uses historical USD/TRY rates. Missing rates will be auto-fetched if enabled.*
                """
            )

            with gr.Accordion("📈 Single Fund Chart", open=True):
                gr.Markdown("#### View a single fund's price history in TRY and USD")

                with gr.Row():
                    chart_ticker = gr.Dropdown(
                        choices=get_unique_tickers() or ["No tickers"],
                        label="Select Fund",
                        value=get_unique_tickers()[0] if get_unique_tickers() else None,
                        interactive=True,
                    )
                    chart_base_date = gr.DateTime(
                        label="Start Date (optional)",
                        value=None,
                        type="string",
                        include_time=False,
                        info="Leave empty for full history",
                    )
                    chart_auto_fetch = gr.Checkbox(label="Auto-fetch missing USD rates", value=True, info="Fetches from Yahoo Finance")
                    btn_generate_chart = gr.Button("📈 Generate Chart", variant="primary")

                chart_status = gr.Textbox(label="Status", interactive=False)
                single_chart = gr.Plot(label="Fund Price Chart")

                btn_generate_chart.click(generate_fund_chart, inputs=[chart_ticker, chart_auto_fetch, chart_base_date], outputs=[single_chart, chart_status])

            with gr.Accordion("📊 Compare Multiple Funds", open=False):
                gr.Markdown(
                    """
                    #### Compare multiple funds on a normalized scale
                    
                    All funds are normalized to **100** at the base date for fair comparison.
                    This shows relative performance regardless of share price.
                    """
                )

                with gr.Row():
                    compare_tickers = gr.Textbox(
                        label="Tickers (comma-separated)",
                        placeholder="MAC, TI2, AFT",
                        value=", ".join(get_unique_tickers()[:3]) if get_unique_tickers() else "",
                    )
                    compare_base_date = gr.DateTime(
                        label="Base Date (optional)",
                        value=None,
                        type="string",
                        include_time=False,
                        info="Normalization start date",
                    )
                with gr.Row():
                    compare_auto_fetch = gr.Checkbox(label="Auto-fetch missing USD rates", value=True)
                    compare_show_usd = gr.Checkbox(label="Show in USD", value=True, info="Convert prices to USD for real comparison")

                btn_compare = gr.Button("📊 Compare Funds", variant="primary")
                compare_status = gr.Textbox(label="Status", interactive=False)
                compare_chart = gr.Plot(label="Fund Comparison Chart")

                btn_compare.click(generate_normalized_chart, inputs=[compare_tickers, compare_auto_fetch, compare_show_usd, compare_base_date], outputs=[compare_chart, compare_status])

            gr.Markdown(
                """
                ---
                **Understanding the Charts:**
                
                - **TRY Price**: Nominal price in Turkish Lira (what you see on TEFAS)
                - **USD Price**: Price converted to USD using historical exchange rates
                - **Normalized (100)**: All funds start at 100 for easy comparison
                
                *A fund that goes from 100 → 120 gained 20%, while one that goes 100 → 80 lost 20%.*
                """
            )

        # ============== TAB 6: HELP ==============
        with gr.Tab("❓ Help"):
            gr.Markdown(
                """
                ## How to Use This App
                
                ### Step 1: Add Your Transactions
                1. Go to the **📊 Transactions** tab
                2. Enter the date you bought, TEFAS fund code (e.g., MAC, TI2), and quantity
                3. **Prices are automatically fetched from TEFAS** - no manual entry needed!
                4. Optionally set the **Tax Rate** (% of TRY gains taxed at sell)
                5. Click "Save Transaction"
                
                ### Step 2: Refresh USD/TRY Rates
                1. Go to the **💵 USD Rates** tab
                2. Click **"Refresh All USD Rates"** - this fetches all historical rates from Yahoo Finance
                3. The system automatically determines the date range needed based on your transactions
                4. All rates are stored in the database for offline use
                
                ### Step 3: Analyze
                1. Go to the **📈 Analyze Returns** tab
                2. Current prices are **auto-filled from TEFAS** data
                3. Click "Update TEFAS Prices" to refresh latest prices
                4. Click "Calculate Real Gains"
                
                ---
                
                ## TEFAS Integration
                
                This app automatically fetches fund prices from [TEFAS](https://www.tefas.gov.tr/):
                - **Buy prices** are looked up based on transaction date
                - **Current prices** are auto-filled in the analysis tab
                - Historical data up to 5 years is fetched for new funds
                
                **Supported funds:** All funds listed on TEFAS (mutual funds, pension funds, ETFs)
                
                ---
                
                ## USD/TRY Rate Management
                
                All USD/TRY rates are stored in the local database:
                - Click **"Refresh All USD Rates"** to fetch all rates from your earliest transaction to today
                - Rates are fetched from Yahoo Finance (USDTRY=X ticker)
                - Once fetched, rates are stored locally and used for all calculations
                - Charts and analysis use the database rates (no external calls during analysis)
                
                ---
                
                ## Understanding Real Returns
                
                **Nominal Return:** How much your investment went up/down in TRY terms (after tax).
                
                **USD Change:** How much TRY lost value against USD.
                
                **Real Return:** Your actual purchasing power gain/loss (after tax).
                
                ### Tax Calculation
                
                Tax is applied only on **TRY gains** (not losses):
                - After-tax value = Current Price - (Gain × Tax Rate)
                - Example: Buy at 0.50, now 0.75, tax 10% → Tax = 0.25 × 10% = 0.025 TRY → After-tax = 0.725 TRY
                
                ---
                
                ## Data Sources
                
                - **Fund Prices**: [TEFAS](https://www.tefas.gov.tr/) (automatic)
                - **CPI**: [TCMB Consumer Prices](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data/Consumer+Prices)
                - **USD/TRY**: Yahoo Finance (USDTRY=X ticker) - stored in local database
                
                The app stores all data in a local SQLite database (`portfolio.db`).
                """
            )

    return demo


def main():
    """Entry point for the application."""
    demo = create_ui()
    demo.launch()


if __name__ == "__main__":
    main()
