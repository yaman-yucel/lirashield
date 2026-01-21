# Turkish Real Return Tracker

A Gradio-based portfolio tracker that calculates inflation-adjusted (real) returns for Turkish mutual fund investments. Tracks portfolio performance against both USD/TRY exchange rates and official CPI data.

## Project Structure

```
├── app.py                    # Entry point (Gradio UI definition)
├── core/                     # Core modules
│   ├── __init__.py
│   ├── database.py           # Database operations with context manager
│   └── analysis.py           # Real return calculations, yfinance integration
├── adapters/                 # External API integrations
│   ├── __init__.py
│   └── tefas.py              # TEFAS price fetching
├── services/                 # Business logic layer
│   ├── __init__.py
│   ├── portfolio.py          # Portfolio/transaction operations
│   ├── rates.py              # USD/CPI rate operations
│   ├── charts.py             # Chart generation
│   └── analysis.py           # Portfolio analysis
├── ui/                       # UI layer
│   ├── __init__.py
│   └── handlers/             # Gradio event handlers
│       ├── __init__.py
│       ├── transactions.py
│       ├── rates.py
│       ├── charts.py
│       └── analysis.py
├── portfolio.db              # SQLite database (auto-created)
├── pyproject.toml            # Project dependencies (uv)
└── uv.lock                   # Locked dependencies
```

## Architecture

The application follows a layered architecture:

```
┌─────────────────────────────────────┐
│           app.py (Gradio UI)        │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│         ui/handlers/ (Event Handlers)│
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│        services/ (Business Logic)    │
└─────────────────┬───────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌───────────────┐
│ core/database │   │   adapters/   │
│ core/analysis │   │  (TEFAS, etc) │
└───────────────┘   └───────────────┘
```

## Running the Application

```bash
# Install dependencies
uv sync

# Run the app
uv run python app.py

# App launches at http://localhost:7860
```

## Core Concepts

### Real Return Formula
```
Real Return = ((1 + Nominal Return) / (1 + Inflation)) - 1
```

If USD rose 20% and your fund rose 20%, your real gain is 0% (you only kept up with inflation).

### Inflation Benchmarks
1. **USD/TRY Exchange Rate** - "Street method" using USD as inflation proxy
2. **Official CPI (TCMB)** - Turkish Central Bank's Consumer Price Index with MoM compounding

### Tax Handling
Tax is applied only on TRY nominal gains (not losses):
```python
after_tax_value = current_price - max(0, gain) * tax_rate
```

## Database Schema (SQLite)

### `transactions` - Portfolio buy transactions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| date | TEXT | Purchase date (YYYY-MM-DD) |
| ticker | TEXT | TEFAS fund code (e.g., MAC, TI2) |
| quantity | REAL | Number of shares |
| tax_rate | REAL | Tax rate on TRY gains (0-100) |
| notes | TEXT | Optional notes |

### `fund_prices` - Historical TEFAS prices
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| date | TEXT | Price date (YYYY-MM-DD) |
| ticker | TEXT | Fund code |
| price | REAL | Price in TRY |
| source | TEXT | Data source (default: 'tefas') |
| UNIQUE(date, ticker) | | Prevents duplicates |

### `cpi_usd_rates` - USD/TRY exchange rates
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| date | TEXT | Rate date (YYYY-MM-DD), UNIQUE |
| usd_try_rate | REAL | USD/TRY exchange rate |
| source | TEXT | 'manual', 'yfinance', 'yfinance_auto' |

### `cpi_official` - TCMB CPI data
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| year_month | TEXT | Month (YYYY-MM), UNIQUE |
| cpi_yoy | REAL | Year-over-Year inflation % |
| cpi_mom | REAL | Month-over-Month inflation % |

## Module Documentation

### `app.py` - Gradio UI

**Entry Point**: Run with `uv run python app.py`

**Tabs**:
1. **Transactions** - Add/delete buy transactions (auto-fetches price from TEFAS)
2. **CPI (TCMB)** - Add/import official CPI data
3. **USD Rates** - Add/fetch USD/TRY rates
4. **Analyze Returns** - Calculate real returns with current prices
5. **Fund Charts** - View price history in TRY/USD
6. **Help** - Usage instructions

### `core/database.py` - Data Layer

**Connection**: Uses context manager for safe database connections:
```python
with get_connection() as conn:
    c = conn.cursor()
    c.execute("SELECT * FROM table")
    # Auto-commits on success, rollbacks on exception, always closes
```

**Key Functions**:
- `init_db()` - Creates tables with migrations for existing DBs
- `add_transaction()` - Looks up price from fund_prices, stores transaction
- `get_fund_price_for_date(ticker, date, exact_match=False)` - Returns price or closest earlier date
- `calculate_cumulative_cpi_daily(start_date, end_date)` - Daily-compounded CPI between dates

### `core/analysis.py` - Calculations

**Key Functions**:
- `get_usd_rate(date, auto_fetch=False)` - Gets rate from DB or yfinance
- `calculate_real_return(buy_price, current_price, buy_date, ...)` - Returns dict with:
  - `nominal_pct` - After-tax nominal return %
  - `usd_inflation_pct` - USD change %
  - `real_return_usd_pct` - Real return vs USD
  - `cpi_inflation_pct` - CPI change %
  - `real_return_cpi_pct` - Real return vs CPI
  - `error` - Error message if both benchmarks fail

### `adapters/tefas.py` - TEFAS Integration

Uses `tefas-crawler` library to fetch fund prices.

**API Limits**: ~90 days per request, uses 60-day chunks

**Key Functions**:
- `fetch_fund_prices(ticker, start_date, end_date)` - Fetches in chunks, bulk inserts
- `update_fund_prices(ticker)` - Only fetches missing recent data
- `fetch_prices_for_new_ticker(ticker, tx_date)` - Fetches 5 years history for new tickers

### `services/` - Business Logic

Services provide a clean interface between UI handlers and data layer:

- **PortfolioService** - Transaction CRUD, TEFAS price management
- **RatesService** - USD/TRY and CPI rate management
- **ChartsService** - Fund price chart generation (TRY/USD)
- **AnalysisService** - Real return calculations

### `ui/handlers/` - Event Handlers

Thin wrappers that connect Gradio events to services:
- `transactions.py` - Add/delete transactions
- `rates.py` - USD and CPI rate management
- `charts.py` - Chart generation
- `analysis.py` - Portfolio analysis

## Data Flow

### Adding a Transaction
```
1. User enters ticker, date, quantity
2. PortfolioService.add_transaction() checks if ticker exists in fund_prices
3. If new ticker: fetch_prices_for_new_ticker() fetches 5 years of history
4. If existing: update_fund_prices() fetches any missing recent data
5. add_transaction() looks up price from fund_prices for the date
6. Transaction stored with auto-fetched price
```

### Calculating Real Returns
```
1. User clicks "Calculate Real Gains"
2. AnalysisService.analyze_portfolio() iterates through transactions
3. For each transaction:
   a. Get current price from price_table (user can edit)
   b. calculate_real_return() computes:
      - Gets buy_date USD rate and today's USD rate
      - Gets cumulative CPI between dates
      - Applies tax on TRY gains
      - Returns nominal, USD-real, CPI-real percentages
4. Summary table shows weighted averages by ticker
```

## Common Issues & Solutions

### Issue: "No price found for TICKER on DATE"
**Cause**: Fund price doesn't exist in fund_prices table for the transaction date
**Solution**: 
- Check if ticker is valid TEFAS fund
- Transaction date might be weekend/holiday - price lookup falls back to earlier date
- Prices are auto-fetched when adding new tickers

### Issue: "Missing both USD and CPI data for DATE"
**Cause**: No inflation data available for comparison
**Solution**:
- Enable "Auto-fetch missing USD rates" checkbox
- Click "Quick Refresh" in USD Rates tab
- Import CPI data in CPI tab

### Issue: TEFAS prices not updating
**Cause**: API limits or market closed
**Solution**:
- `update_fund_prices()` considers data "up to date" if within 3 days (weekend buffer)
- Check if market is open
- Verify ticker is valid TEFAS fund

## Dependencies

```toml
dependencies = [
    "gradio>=5.0.0",        # Web UI framework
    "pandas>=2.0.0",        # Data manipulation
    "tefas-crawler>=0.5.0", # TEFAS price fetcher
    "yfinance>=0.2.0",      # USD/TRY rate fetcher
    "plotly>=5.0.0",        # Interactive charts
]
```

## Type Hints

Project uses Python 3.12+ typing:
- `list[str]` instead of `List[str]`
- `dict[str, float]` instead of `Dict[str, float]`
- `str | None` instead of `Optional[str]`
- `tuple[int, int, str]` for multiple return values

## Key Patterns

### Database Context Manager
```python
with get_connection() as conn:
    c = conn.cursor()
    c.execute("SELECT * FROM table")
    # Auto-commit on success, rollback on error, always close
```

### Service Layer Pattern
```python
# UI handler (thin)
def handle_add_transaction(date, ticker, qty, tax, notes):
    return PortfolioService.add_transaction(date, ticker, qty, tax, notes)

# Service (business logic)
class PortfolioService:
    @staticmethod
    def add_transaction(...):
        # Validation, TEFAS fetch, DB insert
        ...
```

### Date Handling
- All dates stored as `YYYY-MM-DD` strings
- Gradio DateTime returns "YYYY-MM-DD HH:MM:SS", extract first 10 chars: `str(date)[:10]`
- TCMB CPI uses `YYYY-MM` format for months

### Error Handling Pattern
Functions return status strings with emojis:
- `"✅ Success message"` - Operation succeeded
- `"❌ Error: message"` - Operation failed
- `"⚠️ Warning message"` - Partial success or warning
