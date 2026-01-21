# Turkish Real Return Tracker

A Gradio-based portfolio tracker that calculates inflation-adjusted (real) returns for Turkish mutual fund investments. Tracks portfolio performance against both USD/TRY exchange rates and official CPI data.

## Project Structure

```
├── app.py              # Gradio UI and event handlers (main entry point)
├── database.py         # SQLite database operations and schema
├── analysis.py         # Real return calculations and inflation adjustments
├── tefas_fetcher.py    # TEFAS (Turkish fund platform) price fetcher
├── portfolio.db        # SQLite database (auto-created)
├── pyproject.toml      # Project dependencies (uv)
└── uv.lock             # Locked dependencies
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
| price_per_share | REAL | Price from fund_prices table |
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

**Entry Point**: Run with `uv run app.py`

**Tabs**:
1. **Transactions** - Add/delete buy transactions (auto-fetches price from TEFAS)
2. **CPI (TCMB)** - Add/import official CPI data
3. **USD Rates** - Add/fetch USD/TRY rates
4. **Analyze Returns** - Calculate real returns with current prices
5. **Help** - Usage instructions

**Key Functions**:
- `handle_add_transaction()` - Validates ticker via TEFAS, fetches historical prices, stores transaction
- `analyze_portfolio()` - Calculates real returns for all transactions
- `handle_refresh_tefas_prices()` - Updates prices for all portfolio tickers

### `database.py` - Data Layer

**Connection**: Uses `portfolio.db` SQLite database

**Key Functions**:
- `init_db()` - Creates tables with migrations for existing DBs
- `add_transaction()` - Looks up price from fund_prices, stores transaction
- `get_fund_price_for_date(ticker, date, exact_match=False)` - Returns price or closest earlier date
- `calculate_cumulative_cpi_daily(start_date, end_date)` - Daily-compounded CPI between dates

**Price Lookup Logic**:
- Exact match preferred
- Falls back to closest earlier date if `exact_match=False`
- Returns `None` if no data found

### `analysis.py` - Calculations

**Key Functions**:
- `get_usd_rate(date, auto_fetch=False)` - Gets rate from DB or yfinance
- `calculate_real_return(buy_price, current_price, buy_date, ...)` - Returns dict with:
  - `nominal_pct` - After-tax nominal return %
  - `usd_inflation_pct` - USD change %
  - `real_return_usd_pct` - Real return vs USD
  - `cpi_inflation_pct` - CPI change %
  - `real_return_cpi_pct` - Real return vs CPI
  - `error` - Error message if both benchmarks fail

**Auto-fetch Behavior**:
- When `auto_fetch_usd=True`: Only accepts exact date matches from DB, fetches from yfinance if missing
- When `auto_fetch_usd=False`: Falls back to closest earlier date in DB

### `tefas_fetcher.py` - TEFAS Integration

Uses `tefas-crawler` library to fetch fund prices.

**API Limits**: ~90 days per request, uses 60-day chunks

**Key Functions**:
- `fetch_fund_prices(ticker, start_date, end_date)` - Fetches in chunks, bulk inserts
- `update_fund_prices(ticker)` - Only fetches missing recent data
- `fetch_prices_for_new_ticker(ticker, tx_date)` - Fetches 5 years history for new tickers
- `is_valid_tefas_fund(ticker)` - Validates ticker by attempting fetch

## Data Flow

### Adding a Transaction
```
1. User enters ticker, date, quantity
2. handle_add_transaction() checks if ticker exists in fund_prices
3. If new ticker: fetch_prices_for_new_ticker() fetches 5 years of history
4. If existing: update_fund_prices() fetches any missing recent data
5. add_transaction() looks up price from fund_prices for the date
6. Transaction stored with auto-fetched price
```

### Calculating Real Returns
```
1. User clicks "Calculate Real Gains"
2. analyze_portfolio() iterates through transactions
3. For each transaction:
   a. get current price from price_table (user can edit)
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
- Call `fetch_prices_for_new_ticker()` to fetch historical data

### Issue: "Missing both USD and CPI data for DATE"
**Cause**: No inflation data available for comparison
**Solution**:
- Enable "Auto-fetch missing USD rates" checkbox
- Manually add USD rates in USD Rates tab
- Import CPI data in CPI tab

### Issue: TEFAS prices not updating
**Cause**: API limits or market closed
**Solution**:
- `update_fund_prices()` considers data "up to date" if within 3 days (weekend buffer)
- Check if market is open
- Verify ticker is valid TEFAS fund

### Issue: Tax rate shows "0%" but should have value
**Cause**: `tax_rate` column uses NULL/NaN handling
**Solution**: Check `pd.isna()` handling in `analyze_portfolio()`:
```python
tax_rate = 0.0 if pd.isna(tax_rate_raw) else float(tax_rate_raw)
```

## Dependencies

```toml
dependencies = [
    "gradio>=5.0.0",      # Web UI framework
    "pandas>=2.0.0",      # Data manipulation
    "tefas-crawler>=0.5.0", # TEFAS price fetcher
    "yfinance>=0.2.0",    # USD/TRY rate fetcher
]
```

## Running the Application

```bash
# Install dependencies
uv sync

# Run the app
uv run app.py

# App launches at http://localhost:7860
```

## Type Hints

Project uses Python 3.12+ typing:
- `list[str]` instead of `List[str]`
- `dict[str, float]` instead of `Dict[str, float]`
- `str | None` instead of `Optional[str]`
- `tuple[int, int, str]` for multiple return values

## Key Patterns

### Date Handling
- All dates stored as `YYYY-MM-DD` strings
- Gradio DateTime returns "YYYY-MM-DD HH:MM:SS", extract first 10 chars: `str(date)[:10]`
- TCMB CPI uses `YYYY-MM` format for months

### Error Handling Pattern
Functions return status strings with emojis:
- `"✅ Success message"` - Operation succeeded
- `"❌ Error: message"` - Operation failed
- `"⚠️ Warning message"` - Partial success or warning

### Database Pattern
```python
conn = get_connection()
c = conn.cursor()
# ... execute queries ...
conn.commit()  # for writes
conn.close()
```

### Price Fallback Pattern
When exact date not found, fall back to closest earlier date:
```python
c.execute("SELECT price FROM fund_prices WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 1", ...)
```
