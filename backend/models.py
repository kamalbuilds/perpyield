from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Market(BaseModel):
    symbol: str
    mark_price: float = 0.0
    index_price: float = 0.0
    funding_rate: float = 0.0
    next_funding_time: Optional[int] = None
    open_interest: float = 0.0
    volume_24h: float = 0.0


class Position(BaseModel):
    symbol: str
    side: str
    amount: float = 0.0
    entry_price: float = 0.0
    mark_price: float = 0.0
    unrealized_pnl: float = 0.0
    margin: float = 0.0
    leverage: float = 1.0
    funding_earned: float = 0.0


class Order(BaseModel):
    order_id: str
    symbol: str
    side: str
    order_type: str
    price: float = 0.0
    amount: float = 0.0
    filled_amount: float = 0.0
    status: str = "open"
    created_at: Optional[int] = None


class Balance(BaseModel):
    currency: str
    available: float = 0.0
    locked: float = 0.0
    total: float = 0.0


class FundingRate(BaseModel):
    symbol: str
    rate: float = 0.0
    timestamp: int = 0
    annualized_apy: float = 0.0


class VaultState(BaseModel):
    vault_id: str
    total_deposits: float = 0.0
    total_shares: float = 0.0
    current_value: float = 0.0
    positions: list[Position] = Field(default_factory=list)
    strategy: str = "delta_neutral"
    status: str = "inactive"
    created_at: Optional[int] = None
    pnl_history: list[dict] = Field(default_factory=list)


class VaultDeposit(BaseModel):
    user_address: str
    amount: float
    shares: float = 0.0
    timestamp: Optional[int] = None


class BacktestResult(BaseModel):
    strategy: str = "delta_neutral"
    pair: str
    start_date: int = 0
    end_date: int = 0
    total_return_pct: float = 0.0
    annualized_apy: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    funding_earned: float = 0.0
    trading_fees: float = 0.0
    net_pnl: float = 0.0


# --- Request/response models for API ---

class DepositRequest(BaseModel):
    user_address: str
    amount: float


class WithdrawRequest(BaseModel):
    user_address: str
    shares: float
