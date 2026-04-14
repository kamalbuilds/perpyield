from __future__ import annotations

import time
from typing import Optional

import numpy as np

from pacifica.client import PacificaClient, sf

FUNDING_EPOCHS_PER_DAY = 24
MAKER_FEE = 0.0002
TAKER_FEE = 0.0006


def _annualized(daily_avg_yield: float) -> float:
    return ((1 + daily_avg_yield) ** 365 - 1) * 100


class Backtester:
    def __init__(self, client: PacificaClient):
        self.client = client

    async def backtest_funding_strategy(
        self, symbol: str, days: int = 30
    ) -> dict:
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - days * 24 * 3600 * 1000

        candles = await self.client.get_klines(symbol, "1h", start_ms, end_ms)
        if not candles:
            return {
                "symbol": symbol,
                "error": "No kline data returned from Pacifica",
                "days_requested": days,
            }

        closes = []
        funding_rates: list[float] = []

        for c in candles:
            closes.append(sf(c.close))
            funding_rates.append(0.0)

        if len(closes) < 2:
            return {
                "symbol": symbol,
                "error": "Insufficient kline data for backtest",
                "days_requested": days,
                "num_candles": len(closes),
            }

        closes_arr = np.array(closes, dtype=float)
        returns = np.diff(closes_arr) / closes_arr[:-1]

        short_price_pnl = -returns
        fr_arr = np.array(funding_rates[1:], dtype=float)
        funding_income = fr_arr

        combined = short_price_pnl + funding_income
        fee_drag = TAKER_FEE * 2 / len(combined)
        adjusted = combined - fee_drag

        cumulative_curve = np.cumprod(1 + adjusted)
        total_return = cumulative_curve[-1] - 1

        daily_returns_chunked = []
        for i in range(0, len(adjusted), FUNDING_EPOCHS_PER_DAY):
            chunk = adjusted[i : i + FUNDING_EPOCHS_PER_DAY]
            daily_returns_chunked.append(float(np.sum(chunk)))

        avg_daily_yield = float(np.mean(daily_returns_chunked)) if daily_returns_chunked else 0.0

        peak = np.maximum.accumulate(cumulative_curve)
        drawdowns = (cumulative_curve - peak) / peak
        max_drawdown = float(np.min(drawdowns))

        std = float(np.std(adjusted))
        mean = float(np.mean(adjusted))
        sharpe = (mean / std * np.sqrt(365 * 24)) if std > 0 else 0.0

        return {
            "symbol": symbol,
            "days_requested": days,
            "num_periods": len(adjusted),
            "total_pnl_pct": round(total_return * 100, 4),
            "avg_daily_yield": round(avg_daily_yield * 100, 4),
            "annualized": round(_annualized(avg_daily_yield), 4),
            "sharpe": round(float(sharpe), 4),
            "max_drawdown": round(max_drawdown * 100, 4),
        }

    async def backtest_multi_symbol(
        self, symbols: list[str], days: int = 30
    ) -> list[dict]:
        results = []
        for symbol in symbols:
            result = await self.backtest_funding_strategy(symbol, days)
            results.append(result)
        return sorted(
            results,
            key=lambda x: x.get("annualized", float("-inf")),
            reverse=True,
        )
