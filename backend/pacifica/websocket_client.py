from __future__ import annotations
import asyncio
import json
import uuid
import time
import logging
from typing import Callable, Awaitable, Optional

import websockets
from .signing import sign_message

logger = logging.getLogger(__name__)

TESTNET_WS = "wss://test-ws.pacifica.fi/ws"
MAINNET_WS = "wss://ws.pacifica.fi/ws"

Callback = Callable[[dict], Awaitable[None]]


class PacificaWebSocket:
    def __init__(
        self,
        testnet: bool = True,
        private_key: Optional[str] = None,
    ):
        self._url = TESTNET_WS if testnet else MAINNET_WS
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._callbacks: dict[str, list[Callback]] = {}
        self._running = False
        self._keypair = None
        self._public_key: Optional[str] = None
        if private_key:
            from solders.keypair import Keypair
            self._keypair = Keypair.from_base58_string(private_key)
            self._public_key = str(self._keypair.pubkey())

    async def connect(self):
        self._ws = await websockets.connect(self._url, ping_interval=30)
        self._running = True
        asyncio.create_task(self._listen())
        logger.info(f"WebSocket connected to {self._url}")

    async def disconnect(self):
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._callbacks.clear()
        logger.info("WebSocket disconnected")

    def on(self, event: str, callback: Callback):
        self._callbacks.setdefault(event, []).append(callback)

    async def _emit(self, event: str, data: dict):
        for cb in self._callbacks.get(event, []):
            try:
                await cb(data)
            except Exception:
                pass

    async def _listen(self):
        if not self._ws:
            return
        try:
            async for raw in self._ws:
                data = json.loads(raw)
                channel = data.get("channel", data.get("source", data.get("method", "unknown")))
                await self._emit(channel, data)
                await self._emit("*", data)
        except websockets.ConnectionClosed:
            self._running = False
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket listen error: {e}")

    async def _send(self, msg: dict):
        if not self._ws:
            raise RuntimeError("WebSocket not connected")
        await self._ws.send(json.dumps(msg))

    # -- Public subscriptions --

    async def subscribe_prices(self):
        await self._send({"method": "subscribe", "params": {"source": "prices"}})

    async def subscribe_book(self, symbol: str, agg_level: int = 1):
        await self._send({
            "method": "subscribe",
            "params": {"source": "book", "symbol": symbol, "agg_level": agg_level},
        })

    async def subscribe_bbo(self, symbol: str):
        await self._send({
            "method": "subscribe",
            "params": {"source": "bbo", "symbol": symbol},
        })

    async def subscribe_trades(self, symbol: str):
        await self._send({
            "method": "subscribe",
            "params": {"source": "trades", "symbol": symbol},
        })

    async def subscribe_candle(self, symbol: str, resolution: str = "1h"):
        await self._send({
            "method": "subscribe",
            "params": {"source": "candle", "symbol": symbol, "resolution": resolution},
        })

    # -- Authenticated subscriptions --

    async def subscribe_account_positions(self, account: Optional[str] = None):
        addr = account or self._public_key
        if not addr:
            raise ValueError("No account address available")
        await self._send({
            "method": "subscribe",
            "params": {"source": "account_positions", "account": addr},
        })

    async def subscribe_account_orders(self, account: Optional[str] = None):
        addr = account or self._public_key
        if not addr:
            raise ValueError("No account address available")
        await self._send({
            "method": "subscribe",
            "params": {"source": "account_order_updates", "account": addr},
        })

    async def subscribe_account_info(self, account: Optional[str] = None):
        addr = account or self._public_key
        if not addr:
            raise ValueError("No account address available")
        await self._send({
            "method": "subscribe",
            "params": {"source": "account_info", "account": addr},
        })

    async def subscribe_account_trades(self, account: Optional[str] = None):
        addr = account or self._public_key
        if not addr:
            raise ValueError("No account address available")
        await self._send({
            "method": "subscribe",
            "params": {"source": "account_trades", "account": addr},
        })

    # -- WebSocket trading --

    async def ws_create_market_order(
        self,
        symbol: str,
        side: str,
        amount: str,
        reduce_only: bool = False,
        slippage_percent: str = "0.5",
        builder_code: Optional[str] = None,
    ) -> str:
        if not self._keypair:
            raise ValueError("Private key required for trading via WebSocket")
        ts = int(time.time() * 1_000)
        header = {"timestamp": ts, "expiry_window": 5_000, "type": "create_market_order"}
        payload = {
            "symbol": symbol, "side": side, "amount": amount,
            "reduce_only": reduce_only, "slippage_percent": slippage_percent,
            "client_order_id": str(uuid.uuid4()),
        }
        if builder_code:
            payload["builder_code"] = builder_code
        _, sig = sign_message(header, payload, self._keypair)
        req = {
            "account": self._public_key,
            "signature": sig,
            "timestamp": ts,
            "expiry_window": 5_000,
            **payload,
        }
        msg_id = str(uuid.uuid4())
        await self._send({"id": msg_id, "params": {"create_market_order": req}})
        return msg_id

    async def ws_create_limit_order(
        self,
        symbol: str,
        side: str,
        price: str,
        amount: str,
        reduce_only: bool = False,
        tif: str = "GTC",
        builder_code: Optional[str] = None,
    ) -> str:
        if not self._keypair:
            raise ValueError("Private key required for trading via WebSocket")
        ts = int(time.time() * 1_000)
        header = {"timestamp": ts, "expiry_window": 5_000, "type": "create_order"}
        payload = {
            "symbol": symbol, "side": side, "price": price, "amount": amount,
            "reduce_only": reduce_only, "tif": tif,
            "client_order_id": str(uuid.uuid4()),
        }
        if builder_code:
            payload["builder_code"] = builder_code
        _, sig = sign_message(header, payload, self._keypair)
        req = {
            "account": self._public_key,
            "signature": sig,
            "timestamp": ts,
            "expiry_window": 5_000,
            **payload,
        }
        msg_id = str(uuid.uuid4())
        await self._send({"id": msg_id, "params": {"create_order": req}})
        return msg_id
