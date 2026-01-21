"""
LiraShield - Gradio UI Interface

Creates the Gradio blocks UI for portfolio tracking with inflation adjustment.
"""

from datetime import datetime

import gradio as gr
import pandas as pd

from ui.handlers import (
    # Transaction handlers
    handle_add_transaction,
    handle_delete_transaction,
    refresh_portfolio,
    handle_refresh_prices,
    get_ticker_price_table,
    get_unique_tickers,
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
    refresh_rates,
    # Chart handlers
    generate_fund_chart,
    generate_normalized_chart,
    # Analysis handlers
    analyze_portfolio,
    # Refresh handlers
    handle_refresh_cpi_csv,
    handle_quick_check_usdtry,
    handle_long_check_usdtry,
    handle_quick_check_us_stocks,
    handle_long_check_us_stocks,
    handle_quick_check_tefas,
    handle_long_check_tefas,
)


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
                ### Add Transactions (Buy / Sell)
                *Prices are automatically fetched based on asset type: TEFAS for Turkish funds, yfinance for US stocks.*
                *You can also manually enter the buy price - leave empty to auto-fetch.*
                *Sells use FIFO (First In, First Out) to match with oldest buy lots for cost basis calculation.*
                """
            )

            with gr.Row():
                with gr.Column(scale=2):
                    with gr.Row():
                        tx_type = gr.Radio(choices=["Buy", "Sell"], value="Buy", label="Transaction Type", info="Buy = acquire shares, Sell = dispose shares (FIFO matched)")
                        tx_asset_type = gr.Dropdown(
                            choices=["TEFAS Fund (TRY)", "US Stock (USD)", "Cash (TRY)", "Cash (USD)"], value="TEFAS Fund (TRY)", label="Asset Type", info="Select the type of asset"
                        )
                    with gr.Row():
                        tx_date = gr.DateTime(label="Transaction Date", value=datetime.now(), type="string", include_time=False)
                        tx_ticker = gr.Textbox(
                            label="Ticker / Currency", placeholder="e.g., MAC, TI2 (TEFAS) or NVDA, META (US Stock) or TRY/USD (Cash)", max_lines=1, info="For cash, enter TRY or USD"
                        )
                    with gr.Row():
                        tx_qty = gr.Number(label="Quantity / Amount", value=1, minimum=0.0001, precision=4, info="Shares for stocks/funds, amount for cash")
                        tx_buy_price = gr.Number(label="Buy Price (optional)", value=None, minimum=0, precision=6, info="Leave empty to auto-fetch price from TEFAS/yfinance")
                    with gr.Row():
                        tx_tax = gr.Number(label="Tax Rate at Sell (%)", value=0, minimum=0, maximum=100, precision=2, info="Tax on gains (0% for US stocks)")
                    tx_notes = gr.Textbox(label="Notes (optional)", placeholder="e.g., Bought on dip / Sold for profit", max_lines=1)

                    with gr.Row():
                        btn_add_tx = gr.Button("💾 Save Transaction", variant="primary")

                with gr.Column(scale=1):
                    gr.Markdown("### Delete Transaction")
                    del_tx_id = gr.Number(label="Transaction ID to Delete", value=0, minimum=0)
                    btn_del_tx = gr.Button("🗑️ Delete", variant="secondary")

            tx_status = gr.Textbox(label="Status", interactive=False)

            with gr.Row():
                gr.Markdown("### Your Transactions")
                btn_refresh_tx = gr.Button("🔄", variant="secondary", size="sm", scale=0, min_width=40)
            tx_table = gr.Dataframe(
                value=refresh_portfolio(),
                label="Portfolio Transactions",
                interactive=False,
            )

            # Transaction event handlers
            btn_add_tx.click(handle_add_transaction, inputs=[tx_date, tx_ticker, tx_qty, tx_tax, tx_notes, tx_asset_type, tx_type, tx_buy_price], outputs=[tx_status, tx_table])
            btn_del_tx.click(handle_delete_transaction, inputs=[del_tx_id], outputs=[tx_status, tx_table])
            btn_refresh_tx.click(refresh_portfolio, outputs=[tx_table])

        # ============== TAB 2: DATA MANAGEMENT ==============
        with gr.Tab("📊 Data Management"):
            gr.Markdown(
                """
                ### Manage CPI, USD Rates, US Stocks, and TEFAS Stocks Data
                
                View and manage all your data sources in one place.
                """
            )

            # CPI Section
            with gr.Accordion("📊 CPI (TCMB)", open=True):
                gr.Markdown(
                    """
                    **Official CPI Data from Turkish Central Bank (TCMB)**
                    
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

                with gr.Accordion("📥 Bulk Import CPI Data (CSV)", open=False):
                    gr.Markdown(
                        """
                        Paste CSV data from TCMB in format: `month,yoy,mom` (one per line)
                        
                        Supports both `MM-YYYY` and `YYYY-MM` formats.
                        """
                    )
                    bulk_cpi_csv = gr.Textbox(label="CSV Data", placeholder="12-2024,44.38,1.03\n11-2024,47.09,2.24", lines=5)
                    btn_bulk_import_cpi = gr.Button("📥 Import All", variant="primary")

                with gr.Accordion("🔄 Refresh - CSV Import", open=False):
                    gr.Markdown(
                        """
                        **Import CPI data from CSV**
                        
                        Paste CSV data from TCMB in format: `month,yoy,mom` (one per line)
                        Supports both `MM-YYYY` and `YYYY-MM` formats.
                        """
                    )
                    refresh_cpi_csv = gr.Textbox(label="CSV Data", placeholder="12-2024,44.38,1.03\n11-2024,47.09,2.24", lines=5)
                    btn_refresh_cpi_csv = gr.Button("📥 Import CPI CSV", variant="primary")
                    refresh_cpi_status = gr.Textbox(label="Status", interactive=False, lines=3)

                gr.Markdown("### Stored CPI Data")
                cpi_table = gr.Dataframe(
                    value=refresh_cpi(),
                    label="Official CPI Data (TCMB)",
                    interactive=False,
                )
                btn_refresh_cpi = gr.Button("🔄 Refresh Table")

                # CPI event handlers
                btn_add_cpi.click(handle_add_cpi, inputs=[cpi_month, cpi_yoy, cpi_mom, cpi_notes], outputs=[cpi_status, cpi_table])
                btn_del_cpi.click(handle_delete_cpi, inputs=[del_cpi_id], outputs=[cpi_status, cpi_table])
                btn_bulk_import_cpi.click(handle_bulk_import_cpi, inputs=[bulk_cpi_csv], outputs=[cpi_status, cpi_table])
                btn_refresh_cpi_csv.click(handle_refresh_cpi_csv, inputs=[refresh_cpi_csv], outputs=[refresh_cpi_status, cpi_table])
                btn_refresh_cpi.click(refresh_cpi, outputs=[cpi_table])

            gr.Markdown("---")

            # USD Rates Section
            with gr.Accordion("💵 USD/TRY Rates", open=True):
                gr.Markdown(
                    """
                    **USD/TRY Exchange Rates (Inflation Proxy)**
                    
                    The "street method" uses USD/TRY exchange rate changes as an inflation proxy.
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

                with gr.Accordion("🔄 Refresh - API Check", open=False):
                    gr.Markdown(
                        """
                        **Refresh USD/TRY exchange rates from yfinance**
                        
                        - **Quick Check**: Updates from latest stored date to today
                        - **Long Check**: Ensures 5 years of history (fetches 5 years if no entry exists)
                        """
                    )
                    with gr.Row():
                        btn_quick_check_usdtry = gr.Button("⚡ Quick Check USDTRY", variant="primary", size="lg")
                        btn_long_check_usdtry = gr.Button("🔄 Long Check USDTRY", variant="secondary", size="lg")
                    usdtry_status = gr.Textbox(label="Status", interactive=False, lines=4)

                gr.Markdown("### Stored USD/TRY Rates")
                rate_table = gr.Dataframe(
                    value=refresh_rates(),
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
                btn_quick_check_usdtry.click(handle_quick_check_usdtry, outputs=[usdtry_status, rate_table])
                btn_long_check_usdtry.click(handle_long_check_usdtry, outputs=[usdtry_status, rate_table])
                btn_add_rate.click(handle_add_rate, inputs=[rate_date, rate_value, rate_notes], outputs=[rate_status, rate_table])
                btn_fetch_rate.click(handle_fetch_rate, inputs=[rate_date], outputs=[rate_status, rate_table])
                btn_del_rate.click(handle_delete_rate, inputs=[del_rate_id], outputs=[rate_status, rate_table])
                btn_bulk_import.click(handle_bulk_import, inputs=[bulk_csv], outputs=[rate_status, rate_table])

            # US Stocks Section
            with gr.Accordion("📈 US Stocks", open=True):
                gr.Markdown(
                    """
                    **US Stock Prices**
                    
                    Manage and refresh US stock price data from yfinance.
                    """
                )

                with gr.Accordion("🔄 Refresh - API Check", open=False):
                    gr.Markdown(
                        """
                        **Refresh US stock prices from yfinance**
                        
                        Updates prices for all US stocks in your portfolio.
                        - **Quick Check**: Updates from latest stored date to today
                        - **Long Check**: Ensures 5 years of history (fetches 5 years if no entry exists)
                        """
                    )
                    with gr.Row():
                        btn_quick_check_us_stocks = gr.Button("⚡ Quick Check US Stocks", variant="primary", size="lg")
                        btn_long_check_us_stocks = gr.Button("🔄 Long Check US Stocks", variant="secondary", size="lg")
                    us_stocks_status = gr.Textbox(label="Status", interactive=False, lines=4)
                    us_stocks_table = gr.Dataframe(
                        value=pd.DataFrame(),
                        label="US Stocks Status",
                        interactive=False,
                    )
                    btn_quick_check_us_stocks.click(handle_quick_check_us_stocks, outputs=[us_stocks_status, us_stocks_table])
                    btn_long_check_us_stocks.click(handle_long_check_us_stocks, outputs=[us_stocks_status, us_stocks_table])

            gr.Markdown("---")

            # TEFAS Stocks Section
            with gr.Accordion("🏦 TEFAS Stocks", open=True):
                gr.Markdown(
                    """
                    **TEFAS Fund Prices**
                    
                    Manage and refresh TEFAS fund price data from crawler.
                    """
                )

                with gr.Accordion("🔄 Refresh - API Check", open=False):
                    gr.Markdown(
                        """
                        **Refresh TEFAS fund prices from crawler**
                        
                        Updates prices for all TEFAS funds in your portfolio.
                        - **Quick Check**: Updates from latest stored date to today
                        - **Long Check**: Ensures 5 years of history (fetches 5 years if no entry exists)
                        """
                    )
                    with gr.Row():
                        btn_quick_check_tefas = gr.Button("⚡ Quick Check TEFAS", variant="primary", size="lg")
                        btn_long_check_tefas = gr.Button("🔄 Long Check TEFAS", variant="secondary", size="lg")
                    tefas_status = gr.Textbox(label="Status", interactive=False, lines=4)
                    tefas_table = gr.Dataframe(
                        value=pd.DataFrame(),
                        label="TEFAS Stocks Status",
                        interactive=False,
                    )
                    btn_quick_check_tefas.click(handle_quick_check_tefas, outputs=[tefas_status, tefas_table])
                    btn_long_check_tefas.click(handle_long_check_tefas, outputs=[tefas_status, tefas_table])

        # ============== TAB 3: ANALYSIS ==============
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
                    label="Enter current prices for each ticker (auto-filled from price data)",
                    interactive=True,
                    column_count=(3, "fixed"),
                    scale=2,
                )
                with gr.Column(scale=1):
                    btn_refresh_tickers = gr.Button("🔄 Refresh Tickers", variant="secondary")
                    btn_refresh_prices = gr.Button("📈 Update Prices", variant="secondary")
                    auto_fetch_chk = gr.Checkbox(label="Auto-fetch missing USD rates", value=True, info="Fetches from Yahoo Finance")

            price_status = gr.Textbox(label="Price Update Status", interactive=False, visible=True)
            btn_calc = gr.Button("🧮 Calculate Real Gains", variant="primary", size="lg")

            btn_refresh_tickers.click(get_ticker_price_table, outputs=[price_table])
            btn_refresh_prices.click(handle_refresh_prices, outputs=[price_status, price_table])

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
                - 📈 **OPEN** = Unsold position (unrealized gains)
                - ✅ **SOLD** = Closed position (realized gains via FIFO)
                - 🟢 Positive real return (beat inflation)
                - 🔴 Negative real return (inflation won)
                - **Tax** = Tax rate on TRY gains at sell
                - **Nominal** = After-tax nominal return
                - **Unreal P/L** = Unrealized Profit/Loss (open positions)
                - **Realized** = Realized Profit/Loss from sales (FIFO)
                - **Real (USD)** = Weighted average real return vs USD (after tax)
                - **Real (CPI)** = Weighted average real return vs official CPI (after tax)
                
                **FIFO (First In, First Out):** When you sell, the oldest buy lots are matched first.
                """
            )

            # Analysis event handlers
            btn_calc.click(analyze_portfolio, inputs=[price_table, auto_fetch_chk], outputs=[out_table, summary_table, calc_status])

        # ============== TAB 4: FUND CHARTS ==============
        with gr.Tab("📉 Fund Charts"):
            gr.Markdown(
                """
                ### View Fund Price History
                
                View fund prices in both **TRY** and **USD** terms to understand real performance.
                
                *USD conversion uses rates from the database. Fetch rates in the USD Rates tab first.*
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
                    btn_generate_chart = gr.Button("📈 Generate Chart", variant="primary")

                chart_status = gr.Textbox(label="Status", interactive=False)
                single_chart = gr.Plot(label="Fund Price Chart")

                btn_generate_chart.click(generate_fund_chart, inputs=[chart_ticker, chart_base_date], outputs=[single_chart, chart_status])

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
                    compare_show_usd = gr.Checkbox(label="Show in USD", value=True, info="Convert prices to USD for real comparison")

                btn_compare = gr.Button("📊 Compare Funds", variant="primary")
                compare_status = gr.Textbox(label="Status", interactive=False)
                compare_chart = gr.Plot(label="Fund Comparison Chart")

                btn_compare.click(generate_normalized_chart, inputs=[compare_tickers, compare_show_usd, compare_base_date], outputs=[compare_chart, compare_status])

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

        # ============== TAB 5: HELP ==============
        with gr.Tab("❓ Help"):
            gr.Markdown(
                """
                ## How to Use This App
                
                ### Step 1: Add Your Transactions
                1. Go to the **📊 Transactions** tab
                2. Select **Buy** or **Sell** transaction type
                3. Enter the date, TEFAS fund code (e.g., MAC, TI2), and quantity
                4. **Prices are automatically fetched from TEFAS** - no manual entry needed!
                5. Optionally set the **Tax Rate** (% of TRY gains taxed at sell)
                6. Click "Save Transaction"
                
                **Sell Transactions:**
                - When selling, the system validates you have enough shares
                - FIFO (First In, First Out) is used to match sells to buys
                - The oldest lots are sold first, just like real brokerage accounts
                
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
                
                ## FIFO Cost Basis Method
                
                **FIFO (First In, First Out)** is the standard cost basis method used by Turkish and most international brokerages.
                
                **How it works:**
                1. When you **buy** shares, each purchase becomes a "lot" with its own cost basis
                2. When you **sell** shares, the **oldest lots are matched first**
                3. Realized gains/losses are calculated based on the matched lot's original buy price
                
                **Example:**
                - Buy 100 shares @ 10 TRY (Lot 1)
                - Buy 50 shares @ 15 TRY (Lot 2)
                - Sell 120 shares @ 20 TRY
                  - FIFO matches: 100 from Lot 1 + 20 from Lot 2
                  - Realized gain: (100 × 10) + (20 × 5) = 1,100 TRY
                  - Remaining: 30 shares from Lot 2 @ 15 TRY
                
                **Benefits:**
                - Accurate cost basis tracking for tax reporting
                - Separate unrealized (open) and realized (closed) gains
                - Matches how your broker calculates gains
                
                ---
                
                ## What is a Benchmark?
                
                In finance, a **Benchmark** (Karşılaştırma Ölçütü) is a standard or reference point used to evaluate the performance of a security, mutual fund, or investment manager.
                
                **Function:** It serves as a yardstick to determine if an investment is performing better or worse than the general market.
                
                **Common Examples:**
                - **S&P 500** - for US stocks
                - **BIST 100** - for Turkish stocks
                - **USD/TRY** - for Turkish inflation (the "street method")
                - **Official CPI** - for measuring against TCMB inflation data
                
                If a fund's benchmark is BIST 100, the fund manager aims to generate returns higher than that index. 
                
                **In LiraShield**, we use **USD/TRY** and **Official CPI** as benchmarks to measure your *real* purchasing power gains — because beating nominal inflation is what truly matters.
                
                ---
                
                ## Data Sources
                
                - **Fund Prices**: [TEFAS](https://www.tefas.gov.tr/) (automatic)
                - **CPI**: [TCMB Consumer Prices](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data/Consumer+Prices)
                - **USD/TRY**: Yahoo Finance (USDTRY=X ticker) - stored in local database
                
                The app stores all data in a local SQLite database (`portfolio.db`).
                """
            )

    return demo
