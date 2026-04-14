from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


class MarketInfo(BaseModel):
    symbol: str
    tick_size: str = "0"
    min_tick: str = "0"
    max_tick: str = "0"
    lot_size: str = "0"
    max_leverage: int = 1
    isolated_only: bool = False
    min_order_size: str = "0"
    max_order_size: str = "0"
    funding_rate: str = "0"
    next_funding_rate: str = "0"
    created_at: int = 0


class PriceData(BaseModel):
    symbol: str
    mark: str = "0"
    mid: str = "0"
    oracle: str = "0"
    funding: str = "0"
    next_funding: str = "0"
    open_interest: str = "0"
    volume_24h: str = "0"
    yesterday_price: str = "0"
    timestamp: int = 0


class Position(BaseModel):
    symbol: str
    side: str = ""
    amount: str = "0"
    entry_price: str = "0"
    margin: Optional[str] = None
    funding: str = "0"
    isolated: bool = False
    created_at: int = 0
    updated_at: int = 0


class AccountInfo(BaseModel):
    balance: str = "0"
    fee_level: int = 0
    maker_fee: str = "0"
    taker_fee: str = "0"
    account_equity: str = "0"
    available_to_spend: str = "0"
    available_to_withdraw: str = "0"
    pending_balance: str = "0"
    total_margin_used: str = "0"
    cross_mmr: str = "0"
    positions_count: int = 0
    orders_count: int = 0
    stop_orders_count: int = 0
    updated_at: int = 0
    use_ltp_for_stop_orders: bool = False


class OrderInfo(BaseModel):
    order_id: int = 0
    client_order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    price: str = "0"
    initial_amount: str = "0"
    filled_amount: str = "0"
    cancelled_amount: str = "0"
    stop_price: Optional[str] = None
    order_type: str = ""
    stop_parent_order_id: Optional[int] = None
    reduce_only: bool = False
    created_at: int = 0
    updated_at: int = 0


class FundingRecord(BaseModel):
    history_id: int = 0
    symbol: str = ""
    side: str = ""
    amount: str = "0"
    payout: str = "0"
    rate: str = "0"
    created_at: int = 0


class BookLevel(BaseModel):
    p: str = Field(default="0", description="price")
    a: str = Field(default="0", description="amount")
    n: int = Field(default=0, description="order count")


class OrderBookData(BaseModel):
    symbol: str
    bids: list[BookLevel] = Field(default_factory=list)
    asks: list[BookLevel] = Field(default_factory=list)
    timestamp: int | str = 0


class CandleData(BaseModel):
    symbol: str = ""
    open: str = "0"
    high: str = "0"
    low: str = "0"
    close: str = "0"
    volume: str = "0"
    timestamp: int = 0


class BalanceHistory(BaseModel):
    amount: str = "0"
    balance: str = "0"
    pending_balance: str = "0"
    event_type: str = ""
    created_at: int = 0


class TradeRecord(BaseModel):
    history_id: int = 0
    symbol: str = ""
    side: str = ""
    amount: str = "0"
    price: str = "0"
    fee: str = "0"
    created_at: int = 0
