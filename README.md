# LiraShield

**Track your portfolio returns adjusted for inflation using CPI/USD benchmarks.**

LiraShield is a portfolio tracking application that helps you measure your *real* purchasing power gains by calculating returns adjusted for inflation. It uses both USD/TRY exchange rates and official CPI data as benchmarks to show whether your investments are truly beating inflation.

## Features

- **Portfolio Tracking**: Record buy and sell transactions for multiple asset types
- **Multi-Asset Support**:
  - TEFAS funds (Turkish mutual funds)
  - US stocks (via Yahoo Finance)
  - Cash positions (TRY and USD)
- **FIFO Cost Basis**: Uses First In, First Out method for accurate gain/loss calculations
- **Inflation-Adjusted Returns**: Calculates real returns using two benchmarks:
  - **USD/TRY Exchange Rate**: The "street method" for measuring inflation
  - **Official CPI**: Turkish Central Bank (TCMB) consumer price index data
- **Automatic Price Fetching**: Automatically fetches historical and current prices for funds and stocks
- **Real Return Analysis**: Shows both nominal and real (inflation-adjusted) returns with detailed breakdowns
- **Interactive Web UI**: Built with Gradio for easy portfolio management

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd lirashield
```

2. Install dependencies:
```bash
uv sync
```

3. Run the application:
```bash
uv run lirashield-run
```

The application will start a web interface (typically at `http://127.0.0.1:7860`).

## Usage

### Adding Transactions

1. Go to the **Transactions** tab
2. Enter transaction details:
   - Date (YYYY-MM-DD)
   - Ticker symbol (fund code, stock symbol, or TRY/USD for cash)
   - Quantity (always positive)
   - Tax rate (0-100%)
   - Asset type (TEFAS, USD Stock, or Cash)
   - Transaction type (Buy or Sell)
   - Optional: Manual price entry (if left empty, price is auto-fetched)

### Refreshing Prices

1. Go to the **Refresh** tab
2. Click **Refresh All Prices** to update prices for all assets in your portfolio
3. Prices are fetched from:
   - **TEFAS**: For Turkish mutual funds
   - **Yahoo Finance**: For US stocks

### Managing CPI Data

1. Go to the **Data Management** tab
2. In the **CPI (TCMB)** section:
   - Add monthly CPI data manually (Year-Month, YoY rate, MoM rate)
   - Or bulk import from CSV format: `YYYY-MM,CPI_YoY,CPI_MoM`
3. CPI data must be entered manually from [TCMB Consumer Prices](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data/Consumer+Prices)

### Managing USD/TRY Rates

1. Go to the **Data Management** tab
2. In the **USD/TRY Rates** section:
   - Add rates manually (Date, Rate)
   - Or bulk import from CSV format: `YYYY-MM-DD,Rate`
   - Or use the auto-fetch feature to get missing rates from Yahoo Finance

### Analyzing Portfolio

1. Go to the **Analysis** tab
2. Enter current prices for your assets (or use the price table from Refresh tab)
3. View detailed analysis including:
   - Nominal returns vs real returns
   - Comparison against USD/TRY and CPI benchmarks
   - Realized and unrealized gains
   - Portfolio summary with weighted averages

## Data Sources

### Automatic Data Fetching

- **TEFAS Funds**: Prices fetched from TEFAS (Turkey Electronic Fund Trading Platform)
  - Historical data available
  - Daily updates only (not real-time)
  - API limitations: ~90 day chunks per request

- **US Stocks**: Prices fetched from Yahoo Finance (yfinance)
  - Historical data available
  - Daily updates only (not real-time/intraday)
  - Supports most US-listed stocks and ETFs

- **USD/TRY Rates**: Can be auto-fetched from Yahoo Finance
  - Historical rates available
  - Daily updates only

### Manual Data Entry Required

- **CPI Data**: Must be manually entered from TCMB (Turkish Central Bank)
  - Monthly data (Year-Month format)
  - Requires both YoY (Year-over-Year) and MoM (Month-over-Month) rates
  - Available at: [TCMB Consumer Prices](https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Inflation+Data/Consumer+Prices)
  - Can be bulk imported via CSV

- **Historical USD/TRY Rates**: May require manual entry for dates not available via auto-fetch
  - Can be bulk imported via CSV

## Limitations

### Update Frequency

- **Daily Updates Only**: All price data is updated on a daily basis, not in real-time
  - TEFAS funds: Updated once per day after market close
  - US stocks: Updated once per day after market close
  - No intraday price updates available

### Data Sources

- **TEFAS API Limitations**:
  - Requests are chunked into ~60-day periods due to API limits
  - Historical data may have gaps for very old funds
  - Some funds may not have complete historical data

- **Yahoo Finance Limitations**:
  - Rate limiting may apply for bulk requests
  - Some tickers may not be available
  - Historical data availability varies by ticker

### Manual Data Requirements

- **CPI Data**: Must be manually entered each month
  - No automatic fetching available
  - Requires manual data entry from TCMB website
  - CSV bulk import available for efficiency

- **Historical USD/TRY Rates**: May require manual entry for older dates
  - Auto-fetch works for recent dates
  - Historical rates may need manual entry or CSV import

### Other Limitations

- **Single Currency Analysis**: Primarily designed for TRY-based portfolios with USD benchmarks
- **Tax Calculations**: Uses simple tax rate on gains; does not account for complex tax scenarios
- **No Dividend Tracking**: Dividends and distributions are not automatically tracked
- **Local Database**: Data is stored locally in SQLite; no cloud sync

## Project Structure

```
lirashield/
├── adapters/          # Data source adapters (TEFAS, yfinance)
├── core/              # Core functionality (database, analysis, config)
├── services/          # Business logic (portfolio, analysis, rates)
├── ui/                # User interface (Gradio)
│   └── handlers/      # UI event handlers
├── tests/             # Test suite
└── lirashield/        # Application entry point
```

## Development

### Running Tests

```bash
uv run pytest
```

### Dependencies

Key dependencies:
- `gradio`: Web UI framework
- `pandas`: Data manipulation
- `plotly`: Charting
- `tefas-crawler`: TEFAS data fetching
- `yfinance`: Yahoo Finance data fetching

See `pyproject.toml` for complete dependency list.

## License

Do whatever you want

## Contributing

No contribution, private project.
