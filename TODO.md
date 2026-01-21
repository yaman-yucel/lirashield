# System Design Improvements

## Overview

This document outlines architectural improvements for the Turkish Real Return Tracker application.

---

## High Priority

### 1. Database Connection Management

**Problem:** Direct `sqlite3.connect()` calls without context managers can leak connections.

**Tasks:**
- [ ] Add context manager to `get_connection()` in `database.py`
- [ ] Replace all direct connection usage with context manager pattern
- [ ] Add automatic commit/rollback handling

```python
# Target implementation
@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

---

### 2. Split Monolithic UI (app.py)

**Problem:** `app.py` is 1167 lines mixing UI, handlers, and business logic.

**Tasks:**
- [ ] Create `ui/` directory structure
- [ ] Extract transaction handlers to `ui/handlers/transactions.py`
- [ ] Extract rate handlers to `ui/handlers/rates.py`
- [ ] Extract chart generation to `ui/handlers/charts.py`
- [ ] Extract analysis handlers to `ui/handlers/analysis.py`
- [ ] Keep `app.py` as thin orchestration layer

**Target structure:**
```
ui/
├── __init__.py
├── handlers/
│   ├── __init__.py
│   ├── transactions.py
│   ├── rates.py
│   ├── charts.py
│   └── analysis.py
└── components/
    ├── __init__.py
    └── tabs.py
```

---

### 3. Add Service Layer

**Problem:** UI handlers directly call database functions, mixing concerns.

**Tasks:**
- [ ] Create `services/` directory
- [ ] Create `PortfolioService` for transaction operations
- [ ] Create `InflationService` for rate/CPI operations
- [ ] Create `AnalysisService` for return calculations
- [ ] Refactor handlers to use services instead of direct DB calls

```python
# services/portfolio_service.py
class PortfolioService:
    def __init__(self, db: Database):
        self.db = db
    
    def add_transaction(self, date: str, ticker: str, qty: float, tax_rate: float) -> TransactionResult:
        # Validation, TEFAS fetch, DB insert
        ...
    
    def get_portfolio(self) -> list[Transaction]:
        ...
```

---

## Medium Priority

### 4. Domain Models

**Problem:** Data passed as untyped dicts and DataFrames.

**Tasks:**
- [ ] Create `models/` directory
- [ ] Define `Transaction` dataclass
- [ ] Define `FundPrice` dataclass
- [ ] Define `RealReturnResult` dataclass
- [ ] Define `OperationResult` for handler responses
- [ ] Refactor functions to use typed models

```python
# models/transaction.py
from dataclasses import dataclass

@dataclass
class Transaction:
    id: int
    date: str
    ticker: str
    quantity: float
    tax_rate: float
    price_per_share: float | None = None
    notes: str = ""

@dataclass
class OperationResult:
    success: bool
    message: str
    data: Any = None
```

---

### 5. Configuration Management

**Problem:** Hardcoded values scattered throughout codebase.

**Tasks:**
- [ ] Create `config.py` with `Settings` class
- [ ] Move `DB_NAME` to config
- [ ] Move `CHUNK_DAYS` to config
- [ ] Move yfinance ticker symbols to config
- [ ] Add environment variable support

```python
# config.py
from dataclasses import dataclass

@dataclass
class Settings:
    database_path: str = "portfolio.db"
    tefas_chunk_days: int = 60
    tefas_years_back: int = 5
    yfinance_tickers: tuple[str, ...] = ("USDTRY=X", "TRY=X")

settings = Settings()
```

---

### 6. Structured Error Handling

**Problem:** Inconsistent error handling - strings, tuples, exceptions mixed.

**Tasks:**
- [ ] Create `exceptions.py` with custom exception hierarchy
- [ ] Define `ValidationError`, `DataNotFoundError`, `ExternalAPIError`
- [ ] Refactor database functions to raise exceptions
- [ ] Refactor services to raise exceptions
- [ ] Handle exceptions at UI boundary (handlers)

```python
# exceptions.py
class PortfolioError(Exception):
    """Base exception."""

class ValidationError(PortfolioError):
    """Invalid input data."""

class DataNotFoundError(PortfolioError):
    """Required data not available."""

class ExternalAPIError(PortfolioError):
    """External service failed."""
```

---

### 7. External API Abstraction

**Problem:** Direct yfinance/tefas calls with no retry or abstraction.

**Tasks:**
- [ ] Create `adapters/` directory
- [ ] Create `MarketDataProvider` abstract base class
- [ ] Implement `YFinanceAdapter` with retry logic
- [ ] Implement `TEFASAdapter` with retry logic
- [ ] Add in-memory caching for repeated requests
- [ ] Dependency inject adapters into services

---

### 8. Testing Infrastructure

**Problem:** No test infrastructure.

**Tasks:**
- [ ] Add `pytest` to dev dependencies
- [ ] Create `tests/` directory structure
- [ ] Create `conftest.py` with fixtures (test DB, mocks)
- [ ] Write unit tests for `analysis.py` calculations
- [ ] Write unit tests for database operations
- [ ] Write integration tests for services

```
tests/
├── conftest.py
├── unit/
│   ├── test_analysis.py
│   ├── test_models.py
│   └── test_services.py
└── integration/
    └── test_database.py
```

---

## Low Priority

### 9. Repository Pattern

**Tasks:**
- [ ] Create `repositories/` directory
- [ ] Create `TransactionRepository`
- [ ] Create `FundPriceRepository`
- [ ] Create `RateRepository`
- [ ] Abstract SQL queries behind repository methods

---

### 10. Database Schema Improvements

**Tasks:**
- [ ] Add `funds` table for ticker normalization
- [ ] Add foreign key relationships
- [ ] Create proper migration system (consider Alembic)
- [ ] Add indexes for common query patterns

---

### 11. UI Lazy Loading

**Tasks:**
- [ ] Defer expensive data loading until tab is accessed
- [ ] Add loading indicators for async operations
- [ ] Cache chart data to avoid regeneration

---

## Quick Wins

These can be done immediately with minimal risk:

- [ ] Add `conn.row_factory = sqlite3.Row` for dict-like row access
- [ ] Extract `generate_fund_chart()` and `generate_normalized_chart()` to `charts.py`
- [ ] Create simple dataclasses for return types
- [ ] Add type hints to remaining untyped functions
- [ ] Add docstrings to public functions missing them

---

## Target Project Structure

```
portfolio_tracker/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── exceptions.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── transaction.py
│   │   ├── price.py
│   │   └── result.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── portfolio.py
│   │   ├── inflation.py
│   │   └── analysis.py
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── tefas.py
│   │   └── yfinance.py
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── transactions.py
│   │   ├── prices.py
│   │   └── rates.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── migrations.py
│   │
│   └── ui/
│       ├── __init__.py
│       ├── app.py
│       ├── handlers/
│       └── components/
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
├── pyproject.toml
├── TODO.md
└── README.md
```

---

## Implementation Order

1. **Database context manager** - Prevents resource leaks (30 min)
2. **Extract chart functions** - Reduces app.py complexity (1 hr)
3. **Add domain models** - Type safety foundation (1 hr)
4. **Create config.py** - Centralize settings (30 min)
5. **Add exceptions.py** - Error handling foundation (30 min)
6. **Create service layer** - Business logic separation (2-3 hrs)
7. **Add pytest infrastructure** - Enable testing (1 hr)
8. **Refactor handlers** - Use services (2-3 hrs)
