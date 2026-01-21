"""
FIFO (First In, First Out) cost basis calculation service.

Handles matching sell transactions to buy transactions in chronological order
to calculate realized gains/losses and remaining holdings.
"""

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from core.database import TX_BUY, TX_SELL, get_portfolio


@dataclass
class LotMatch:
    """Represents a matched lot from FIFO processing."""

    buy_date: str
    buy_price: float
    sell_date: str
    sell_price: float
    quantity: float
    cost_basis: float  # buy_price * quantity
    proceeds: float  # sell_price * quantity
    realized_gain: float  # proceeds - cost_basis
    realized_gain_pct: float  # (realized_gain / cost_basis) * 100
    holding_days: int
    tax_rate: float


@dataclass
class OpenLot:
    """Represents an open (unsold) lot."""

    buy_id: int
    buy_date: str
    buy_price: float
    quantity: float
    remaining_quantity: float
    cost_basis: float
    tax_rate: float
    asset_type: str
    currency: str


@dataclass
class FIFOResult:
    """Result of FIFO analysis for a single ticker."""

    ticker: str
    asset_type: str
    currency: str
    open_lots: list[OpenLot] = field(default_factory=list)
    closed_lots: list[LotMatch] = field(default_factory=list)
    total_shares_held: float = 0.0
    total_cost_basis: float = 0.0
    avg_cost_per_share: float = 0.0
    total_realized_gain: float = 0.0
    total_proceeds: float = 0.0


def calculate_fifo_for_ticker(df: pd.DataFrame, ticker: str) -> FIFOResult:
    """
    Calculate FIFO cost basis for a single ticker.

    Args:
        df: DataFrame with all transactions (from get_portfolio())
        ticker: The ticker symbol to analyze

    Returns:
        FIFOResult with open lots, closed lots, and summary stats
    """
    # Filter for this ticker and sort by date ascending (oldest first for FIFO)
    ticker_df = df[df["ticker"] == ticker].sort_values("date", ascending=True)

    if ticker_df.empty:
        return FIFOResult(ticker=ticker, asset_type="", currency="")

    # Get asset type and currency from first transaction
    first_row = ticker_df.iloc[0]
    asset_type = first_row.get("asset_type", "TEFAS")
    currency = first_row.get("currency", "TRY")

    # Track open lots (FIFO queue)
    open_lots: list[OpenLot] = []
    closed_lots: list[LotMatch] = []

    for _, row in ticker_df.iterrows():
        tx_type = row.get("transaction_type", TX_BUY)
        quantity = float(row["quantity"])
        price = float(row["price_per_share"]) if pd.notna(row["price_per_share"]) else 0.0
        date = row["date"]
        tax_rate = float(row.get("tax_rate", 0)) if pd.notna(row.get("tax_rate")) else 0.0
        tx_id = int(row["id"])

        if tx_type == TX_BUY:
            # Add new lot to the queue
            lot = OpenLot(
                buy_id=tx_id,
                buy_date=date,
                buy_price=price,
                quantity=quantity,
                remaining_quantity=quantity,
                cost_basis=price * quantity,
                tax_rate=tax_rate,
                asset_type=asset_type,
                currency=currency,
            )
            open_lots.append(lot)

        elif tx_type == TX_SELL:
            # Match sell to oldest lots (FIFO)
            sell_quantity_remaining = quantity
            sell_price = price
            sell_date = date

            while sell_quantity_remaining > 0 and open_lots:
                oldest_lot = open_lots[0]

                if oldest_lot.remaining_quantity <= sell_quantity_remaining:
                    # Fully consume this lot
                    matched_qty = oldest_lot.remaining_quantity
                    sell_quantity_remaining -= matched_qty

                    cost_basis = oldest_lot.buy_price * matched_qty
                    proceeds = sell_price * matched_qty
                    realized_gain = proceeds - cost_basis
                    realized_gain_pct = (realized_gain / cost_basis * 100) if cost_basis > 0 else 0

                    # Calculate holding days
                    buy_dt = datetime.strptime(oldest_lot.buy_date, "%Y-%m-%d")
                    sell_dt = datetime.strptime(sell_date, "%Y-%m-%d")
                    holding_days = (sell_dt - buy_dt).days

                    closed_lots.append(
                        LotMatch(
                            buy_date=oldest_lot.buy_date,
                            buy_price=oldest_lot.buy_price,
                            sell_date=sell_date,
                            sell_price=sell_price,
                            quantity=matched_qty,
                            cost_basis=cost_basis,
                            proceeds=proceeds,
                            realized_gain=realized_gain,
                            realized_gain_pct=realized_gain_pct,
                            holding_days=holding_days,
                            tax_rate=oldest_lot.tax_rate,
                        )
                    )

                    # Remove fully consumed lot
                    open_lots.pop(0)

                else:
                    # Partially consume this lot
                    matched_qty = sell_quantity_remaining
                    sell_quantity_remaining = 0

                    cost_basis = oldest_lot.buy_price * matched_qty
                    proceeds = sell_price * matched_qty
                    realized_gain = proceeds - cost_basis
                    realized_gain_pct = (realized_gain / cost_basis * 100) if cost_basis > 0 else 0

                    # Calculate holding days
                    buy_dt = datetime.strptime(oldest_lot.buy_date, "%Y-%m-%d")
                    sell_dt = datetime.strptime(sell_date, "%Y-%m-%d")
                    holding_days = (sell_dt - buy_dt).days

                    closed_lots.append(
                        LotMatch(
                            buy_date=oldest_lot.buy_date,
                            buy_price=oldest_lot.buy_price,
                            sell_date=sell_date,
                            sell_price=sell_price,
                            quantity=matched_qty,
                            cost_basis=cost_basis,
                            proceeds=proceeds,
                            realized_gain=realized_gain,
                            realized_gain_pct=realized_gain_pct,
                            holding_days=holding_days,
                            tax_rate=oldest_lot.tax_rate,
                        )
                    )

                    # Update remaining quantity in lot
                    oldest_lot.remaining_quantity -= matched_qty
                    oldest_lot.cost_basis = oldest_lot.buy_price * oldest_lot.remaining_quantity

    # Calculate summary stats
    total_shares = sum(lot.remaining_quantity for lot in open_lots)
    total_cost_basis = sum(lot.cost_basis for lot in open_lots)
    avg_cost = total_cost_basis / total_shares if total_shares > 0 else 0
    total_realized = sum(lot.realized_gain for lot in closed_lots)
    total_proceeds = sum(lot.proceeds for lot in closed_lots)

    return FIFOResult(
        ticker=ticker,
        asset_type=asset_type,
        currency=currency,
        open_lots=open_lots,
        closed_lots=closed_lots,
        total_shares_held=total_shares,
        total_cost_basis=total_cost_basis,
        avg_cost_per_share=avg_cost,
        total_realized_gain=total_realized,
        total_proceeds=total_proceeds,
    )


def calculate_fifo_all_tickers() -> dict[str, FIFOResult]:
    """
    Calculate FIFO cost basis for all tickers in the portfolio.

    Returns:
        Dictionary mapping ticker -> FIFOResult
    """
    df = get_portfolio()
    if df.empty:
        return {}

    tickers = df["ticker"].unique()
    results = {}

    for ticker in tickers:
        results[ticker] = calculate_fifo_for_ticker(df, ticker)

    return results


def get_open_positions() -> pd.DataFrame:
    """
    Get all open (unsold) positions with FIFO cost basis.

    Returns:
        DataFrame with columns: ticker, buy_date, buy_price, quantity,
        cost_basis, tax_rate, asset_type, currency
    """
    fifo_results = calculate_fifo_all_tickers()

    rows = []
    for ticker, result in fifo_results.items():
        for lot in result.open_lots:
            rows.append(
                {
                    "ticker": ticker,
                    "buy_id": lot.buy_id,
                    "buy_date": lot.buy_date,
                    "buy_price": lot.buy_price,
                    "quantity": lot.remaining_quantity,
                    "cost_basis": lot.cost_basis,
                    "tax_rate": lot.tax_rate,
                    "asset_type": lot.asset_type,
                    "currency": lot.currency,
                }
            )

    if not rows:
        return pd.DataFrame(columns=["ticker", "buy_id", "buy_date", "buy_price", "quantity", "cost_basis", "tax_rate", "asset_type", "currency"])

    return pd.DataFrame(rows).sort_values(["ticker", "buy_date"])


def get_realized_gains() -> pd.DataFrame:
    """
    Get all realized gains/losses from closed positions.

    Returns:
        DataFrame with columns: ticker, buy_date, sell_date, buy_price, sell_price,
        quantity, cost_basis, proceeds, realized_gain, realized_gain_pct, holding_days
    """
    fifo_results = calculate_fifo_all_tickers()

    rows = []
    for ticker, result in fifo_results.items():
        for lot in result.closed_lots:
            rows.append(
                {
                    "ticker": ticker,
                    "buy_date": lot.buy_date,
                    "sell_date": lot.sell_date,
                    "buy_price": lot.buy_price,
                    "sell_price": lot.sell_price,
                    "quantity": lot.quantity,
                    "cost_basis": lot.cost_basis,
                    "proceeds": lot.proceeds,
                    "realized_gain": lot.realized_gain,
                    "realized_gain_pct": lot.realized_gain_pct,
                    "holding_days": lot.holding_days,
                    "tax_rate": lot.tax_rate,
                    "currency": result.currency,
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["ticker", "buy_date", "sell_date", "buy_price", "sell_price", "quantity", "cost_basis", "proceeds", "realized_gain", "realized_gain_pct", "holding_days", "tax_rate", "currency"]
        )

    return pd.DataFrame(rows).sort_values(["sell_date", "ticker"], ascending=[False, True])


def get_portfolio_summary() -> pd.DataFrame:
    """
    Get summary by ticker including both open and closed positions.

    Returns:
        DataFrame with columns: ticker, shares_held, avg_cost, cost_basis,
        realized_gain, realized_proceeds, asset_type, currency
    """
    fifo_results = calculate_fifo_all_tickers()

    rows = []
    for ticker, result in fifo_results.items():
        rows.append(
            {
                "ticker": ticker,
                "shares_held": result.total_shares_held,
                "avg_cost": result.avg_cost_per_share,
                "cost_basis": result.total_cost_basis,
                "realized_gain": result.total_realized_gain,
                "realized_proceeds": result.total_proceeds,
                "asset_type": result.asset_type,
                "currency": result.currency,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["ticker", "shares_held", "avg_cost", "cost_basis", "realized_gain", "realized_proceeds", "asset_type", "currency"])

    return pd.DataFrame(rows).sort_values("ticker")
