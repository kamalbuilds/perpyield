from __future__ import annotations
import asyncio
import logging
import random
import time
import uuid
from typing import Optional

import base58
import httpx

from .signing import sign_message
from .models import (
    MarketInfo, PriceData, Position, AccountInfo, OrderInfo,
    FundingRecord, OrderBookData, BookLevel, CandleData, BalanceHistory,
    TradeRecord,
)

logger = logging.getLogger(__name__)

TESTNET_REST = "https://test-api.pacifica.fi/api/v1"
MAINNET_REST = "https://api.pacifica.fi/api/v1"
EXPIRY_WINDOW = 5_000


def sf(val, default=0.0) -> float:
    """Safe float conversion for string or None values."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class PacificaClient:
    def __init__(
        self,
        private_key: Optional[str] = None,
        testnet: bool = True,
        builder_code: Optional[str] = None,
        agent_wallet_key: Optional[str] = None,
    ):
        self._base = TESTNET_REST if testnet else MAINNET_REST
        self._builder_code = builder_code
        self._http = httpx.AsyncClient(
            base_url=self._base,
            timeout=30.0,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        self.keypair = None
        self.public_key: Optional[str] = None
        self._agent_keypair = None
        self._agent_pubkey: Optional[str] = None

        if private_key and private_key.strip():
            from solders.keypair import Keypair
            try:
                self.keypair = Keypair.from_base58_string(private_key.strip())
            except Exception:
                raw = base58.b58decode(private_key.strip())
                self.keypair = Keypair.from_bytes(raw)
            self.public_key = str(self.keypair.pubkey())

        if agent_wallet_key and agent_wallet_key.strip():
            from solders.keypair import Keypair
            self._agent_keypair = Keypair.from_base58_string(agent_wallet_key.strip())
            self._agent_pubkey = str(self._agent_keypair.pubkey())

    @property
    def address(self) -> Optional[str]:
        return self.public_key

    @property
    def builder_code(self) -> Optional[str]:
        return self._builder_code

    def _signing_keypair(self):
        return self._agent_keypair if self._agent_keypair else self.keypair

    def _ts(self) -> int:
        return int(time.time() * 1_000)

    def _build_signed_request(self, msg_type: str, payload: dict) -> dict:
        if not self.keypair:
            raise RuntimeError("Private key required for signed requests. Set PACIFICA_PRIVATE_KEY in .env")
        header = {"timestamp": self._ts(), "expiry_window": EXPIRY_WINDOW, "type": msg_type}
        _, signature = sign_message(header, payload, self._signing_keypair())
        req = {
            "account": self.public_key,
            "signature": signature,
            "timestamp": header["timestamp"],
            "expiry_window": header["expiry_window"],
            **payload,
        }
        if self._agent_pubkey:
            req["agent_wallet"] = self._agent_pubkey
        return req

    async def _get(self, path: str, params: Optional[dict] = None, retries: int = 4):
        for attempt in range(retries):
            resp = await self._http.get(path, params=params)
            if resp.status_code == 429:
                wait = min(2 ** (attempt + 1), 16) + random.uniform(0.5, 2.0)
                logger.warning(f"Rate limited on {path}, retrying in {wait:.1f}s")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    async def _signed_post(self, path: str, msg_type: str, payload: dict) -> dict:
        req = self._build_signed_request(msg_type, payload)
        resp = await self._http.post(path, json=req)
        resp.raise_for_status()
        return resp.json()

    async def aclose(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def close(self):
        await self.aclose()

    # -- Market Data (public) --

    async def get_markets(self) -> list[MarketInfo]:
        r = await self._get("/info")
        data = r.get("data", r.get("result", [r])) if isinstance(r, dict) else r
        return [MarketInfo(**m) if isinstance(m, dict) else m for m in data]

    async def get_market_info(self) -> list[MarketInfo]:
        return await self.get_markets()

    async def get_prices(self) -> list[PriceData]:
        r = await self._get("/info/prices")
        data = r.get("data", r.get("result", [r])) if isinstance(r, dict) else r
        return [PriceData(**p) if isinstance(p, dict) else p for p in data]

    async def get_price(self, symbol: str) -> Optional[PriceData]:
        prices = await self.get_prices()
        for p in prices:
            if p.symbol == symbol:
                return p
        return None

    async def get_orderbook(self, symbol: str, agg_level: int = 1) -> OrderBookData:
        r = await self._get("/book", params={"symbol": symbol, "agg_level": agg_level})
        d = r.get("data", r)
        bids = [BookLevel(**lvl) for lvl in d["l"][0]] if len(d.get("l", [])) > 0 else []
        asks = [BookLevel(**lvl) for lvl in d["l"][1]] if len(d.get("l", [])) > 1 else []
        return OrderBookData(symbol=d.get("s", symbol), bids=bids, asks=asks, timestamp=d.get("t", 0))

    async def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[CandleData]:
        if start_time is None:
            start_time = int(time.time() * 1_000) - 24 * 3600 * 1_000
        params: dict = {"symbol": symbol, "interval": interval, "start_time": start_time}
        if end_time is not None:
            params["end_time"] = end_time
        r = await self._get("/kline", params=params)
        data = r.get("data", r.get("result", [])) if isinstance(r, dict) else r
        candles = []
        for c in data:
            if isinstance(c, dict):
                candles.append(CandleData(
                    symbol=symbol,
                    open=str(c.get("o", c.get("open", "0"))),
                    high=str(c.get("h", c.get("high", "0"))),
                    low=str(c.get("l", c.get("low", "0"))),
                    close=str(c.get("c", c.get("close", "0"))),
                    volume=str(c.get("v", c.get("volume", "0"))),
                    timestamp=c.get("t", c.get("timestamp", 0)),
                ))
        return candles

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: Optional[int] = None,
    ) -> list[CandleData]:
        return await self.get_candles(symbol, interval, start_time, end_time)

    async def get_funding_rates(self) -> dict[str, dict]:
        prices = await self.get_prices()
        return {
            p.symbol: {
                "current": p.funding,
                "next": p.next_funding,
                "mark": p.mark,
                "oracle": p.oracle,
                "funding": p.funding,
                "next_funding": p.next_funding,
                "open_interest": p.open_interest,
                "volume_24h": p.volume_24h,
            }
            for p in prices
        }

    async def get_market_funding_history(
        self, symbol: str, limit: int = 100, cursor: Optional[str] = None
    ) -> dict:
        params: dict = {"symbol": symbol, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self._get("/funding_rate/history", params=params)

    # -- Account Data (public reads) --

    async def get_account(self, account: Optional[str] = None) -> AccountInfo:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required. Set PACIFICA_PRIVATE_KEY in .env")
        r = await self._get("/account", params={"account": addr})
        data = r.get("data", r) if isinstance(r, dict) else r
        return AccountInfo(**data) if isinstance(data, dict) else AccountInfo()

    async def get_positions(self, account: Optional[str] = None) -> list[Position]:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        r = await self._get("/positions", params={"account": addr})
        data = r.get("data", []) if isinstance(r, dict) else r
        return [Position(**p) if isinstance(p, dict) else p for p in data]

    async def get_open_orders(self, account: Optional[str] = None) -> list[OrderInfo]:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        r = await self._get("/orders", params={"account": addr})
        data = r.get("data", r.get("result", [])) if isinstance(r, dict) else r
        return [OrderInfo(**o) if isinstance(o, dict) else o for o in data]

    async def get_orders(self, account: Optional[str] = None, symbol: Optional[str] = None) -> list[OrderInfo]:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        params: dict = {"account": addr}
        if symbol:
            params["symbol"] = symbol
        r = await self._get("/orders", params=params)
        data = r.get("data", r.get("result", [])) if isinstance(r, dict) else r
        return [OrderInfo(**o) if isinstance(o, dict) else o for o in data]

    async def get_funding_history(
        self, account: Optional[str] = None, limit: int = 50, cursor: Optional[str] = None
    ) -> dict:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        params: dict = {"account": addr, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = await self._get("/funding/history", params=params)
        body = r if isinstance(r, dict) else {"data": []}
        records = [FundingRecord(**f) for f in body.get("data", [])]
        return {"records": records, "next_cursor": body.get("next_cursor"), "has_more": body.get("has_more", False)}

    async def get_balance_history(
        self, account: Optional[str] = None, limit: int = 50, cursor: Optional[str] = None
    ) -> dict:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        params: dict = {"account": addr, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = await self._get("/account/balance/history", params=params)
        body = r if isinstance(r, dict) else {"data": []}
        records = [BalanceHistory(**b) for b in body.get("data", [])]
        return {"records": records, "next_cursor": body.get("next_cursor"), "has_more": body.get("has_more", False)}

    async def get_trade_history(
        self, account: Optional[str] = None, limit: int = 50, cursor: Optional[str] = None
    ) -> dict:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        params: dict = {"account": addr, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        r = await self._get("/account/trades", params=params)
        body = r if isinstance(r, dict) else {"data": []}
        records = [TradeRecord(**t) for t in body.get("data", [])]
        return {"records": records, "next_cursor": body.get("next_cursor"), "has_more": body.get("has_more", False)}

    async def get_funding_payments(
        self, account: Optional[str] = None, symbol: Optional[str] = None, limit: int = 100
    ) -> list[FundingRecord]:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        params: dict = {"account": addr, "limit": limit}
        if symbol:
            params["symbol"] = symbol
        r = await self._get("/funding_rate/payments", params=params)
        data = r.get("data", r.get("result", [])) if isinstance(r, dict) else r
        return [FundingRecord(**f) if isinstance(f, dict) else f for f in data]

    async def get_balances(self, account: Optional[str] = None) -> list[dict]:
        addr = account or self.public_key
        if not addr:
            raise RuntimeError("Account address required")
        r = await self._get("/account/balances", params={"account": addr})
        data = r.get("data", r.get("result", [r])) if isinstance(r, dict) else r
        return data if isinstance(data, list) else []

    async def get_trades(self, symbol: str, limit: int = 100) -> list[dict]:
        r = await self._get("/trades", params={"symbol": symbol, "limit": limit})
        data = r.get("data", r.get("result", [])) if isinstance(r, dict) else r
        return data if isinstance(data, list) else []

    # -- Orders (signed) --

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: str,
        reduce_only: bool = False,
        slippage_percent: str = "0.5",
        client_order_id: Optional[str] = None,
        builder_code: Optional[str] = None,
    ) -> dict:
        payload = {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "reduce_only": reduce_only,
            "slippage_percent": slippage_percent,
            "client_order_id": client_order_id or str(uuid.uuid4()),
        }
        bc = builder_code or self._builder_code
        if bc:
            payload["builder_code"] = bc
        return await self._signed_post("/orders/create_market", "create_market_order", payload)

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        price: str,
        amount: str,
        reduce_only: bool = False,
        tif: str = "GTC",
        client_order_id: Optional[str] = None,
        builder_code: Optional[str] = None,
    ) -> dict:
        payload = {
            "symbol": symbol,
            "side": side,
            "price": price,
            "amount": amount,
            "reduce_only": reduce_only,
            "tif": tif,
            "client_order_id": client_order_id or str(uuid.uuid4()),
        }
        bc = builder_code or self._builder_code
        if bc:
            payload["builder_code"] = bc
        return await self._signed_post("/orders/create", "create_order", payload)

    async def cancel_order(
        self, symbol: str, order_id: Optional[int] = None, client_order_id: Optional[str] = None
    ) -> dict:
        if not order_id and not client_order_id:
            raise ValueError("Either order_id or client_order_id required")
        payload: dict = {"symbol": symbol}
        if order_id:
            payload["order_id"] = order_id
        if client_order_id:
            payload["client_order_id"] = client_order_id
        return await self._signed_post("/orders/cancel", "cancel_order", payload)

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> dict:
        payload: dict = {}
        if symbol:
            payload["symbol"] = symbol
        return await self._signed_post("/orders/cancel_all", "cancel_all_orders", payload)

    async def batch_orders(self, actions: list[dict]) -> dict:
        resp = await self._http.post("/orders/batch", json={"actions": actions})
        resp.raise_for_status()
        return resp.json()

    def build_batch_create(self, symbol: str, side: str, price: str, amount: str, tif: str = "GTC") -> dict:
        payload = {
            "symbol": symbol, "side": side, "price": price, "amount": amount,
            "reduce_only": False, "tif": tif, "client_order_id": str(uuid.uuid4()),
        }
        if self._builder_code:
            payload["builder_code"] = self._builder_code
        req = self._build_signed_request("create_order", payload)
        return {"type": "Create", "data": req}

    def build_batch_cancel(self, symbol: str, order_id: int) -> dict:
        payload = {"symbol": symbol, "order_id": order_id}
        req = self._build_signed_request("cancel_order", payload)
        return {"type": "Cancel", "data": req}

    # -- Position Management (signed) --

    async def set_tpsl(
        self,
        symbol: str,
        side: str,
        take_profit: Optional[dict] = None,
        stop_loss: Optional[dict] = None,
        tp_price: Optional[str] = None,
        sl_price: Optional[str] = None,
    ) -> dict:
        payload: dict = {"symbol": symbol, "side": side}
        if take_profit:
            tp = {"stop_price": take_profit["stop_price"]}
            if "limit_price" in take_profit:
                tp["limit_price"] = take_profit["limit_price"]
            if "amount" in take_profit:
                tp["amount"] = take_profit["amount"]
            tp["client_order_id"] = str(uuid.uuid4())
            payload["take_profit"] = tp
        elif tp_price:
            payload["tp_price"] = tp_price
        if stop_loss:
            sl = {"stop_price": stop_loss["stop_price"]}
            if "limit_price" in stop_loss:
                sl["limit_price"] = stop_loss["limit_price"]
            if "amount" in stop_loss:
                sl["amount"] = stop_loss["amount"]
            payload["stop_loss"] = sl
        elif sl_price:
            payload["sl_price"] = sl_price
        return await self._signed_post("/positions/tpsl", "set_position_tpsl", payload)

    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        return await self._signed_post("/account/leverage", "set_leverage", {"symbol": symbol, "leverage": leverage})

    async def update_leverage(self, symbol: str, leverage: int) -> dict:
        return await self.set_leverage(symbol, leverage)

    # -- Agent Wallet --

    async def bind_agent_wallet(self, agent_wallet_pubkey: str) -> dict:
        payload = {"agent_wallet": agent_wallet_pubkey}
        return await self._signed_post("/agent/bind", "bind_agent_wallet", payload)

    # -- Lake (Vault) Operations --

    async def create_lake(self, nickname: Optional[str] = None) -> dict:
        if not self.public_key:
            raise ValueError("No private key configured")
        payload: dict = {"manager": self.public_key}
        if nickname:
            payload["nickname"] = nickname
        return await self._signed_post("/lake/create", "create_lake", payload)

    async def deposit_to_lake(self, lake_address: str, amount: str) -> dict:
        return await self._signed_post("/lake/deposit", "deposit_lake", {"lake": lake_address, "amount": amount})

    async def lake_deposit(self, lake_address: str, amount: str) -> dict:
        return await self.deposit_to_lake(lake_address, amount)

    async def withdraw_from_lake(self, lake_address: str, shares: str) -> dict:
        return await self._signed_post("/lake/withdraw", "withdraw_lake", {"lake": lake_address, "shares": shares})

    async def lake_withdraw(self, lake_address: str, amount: str) -> dict:
        return await self.withdraw_from_lake(lake_address, amount)
