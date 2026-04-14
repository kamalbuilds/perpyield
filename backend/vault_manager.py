from __future__ import annotations

from pacifica.client import PacificaClient


class VaultManager:
    def __init__(self, client: PacificaClient):
        self.client = client

    async def create_vault(self, name: str) -> dict:
        return await self.client.create_lake(name)

    async def get_vault_status(self, lake_address: str) -> dict:
        return {
            "lake_address": lake_address,
            "status": "unknown",
            "note": "Lake status endpoint TBD, not yet available in Pacifica API v1",
        }

    async def rebalance_vault(self, lake_address: str, strategy_signals: list[dict]) -> dict:
        if not strategy_signals:
            return {"lake_address": lake_address, "trades": [], "message": "No signals provided"}

        trades = []
        for signal in strategy_signals:
            symbol = signal.get("symbol")
            direction = signal.get("direction", "short")
            size = signal.get("size", "0")
            if not symbol or not size or float(size) <= 0:
                continue

            side = "ask" if direction == "short" else "bid"
            try:
                result = await self.client.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=str(size),
                    slippage_percent="0.5",
                )
                trades.append({"symbol": symbol, "side": side, "size": size, "result": result})
            except Exception as exc:
                trades.append({"symbol": symbol, "side": side, "size": size, "error": str(exc)})

        return {
            "lake_address": lake_address,
            "trades_attempted": len(trades),
            "trades": trades,
        }

    async def deposit(self, lake_address: str, amount: str) -> dict:
        return await self.client.deposit_to_lake(lake_address, amount)

    async def withdraw(self, lake_address: str, shares: str) -> dict:
        return await self.client.withdraw_from_lake(lake_address, shares)
