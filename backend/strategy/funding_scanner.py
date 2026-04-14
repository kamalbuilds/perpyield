import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from pacifica.client import PacificaClient, sf


@dataclass
class FundingOpportunity:
    symbol: str
    funding_rate: float
    next_funding_rate: float
    apy_current: float
    apy_next: float
    mark_price: float
    oracle_price: float
    open_interest: float
    volume_24h: float
    max_leverage: int
    trend: str


@dataclass
class FundingHistory:
    symbol: str
    rates: list[dict] = field(default_factory=list)
    avg_rate_24h: float = 0.0
    avg_rate_7d: float = 0.0
    positive_rate_pct: float = 0.0


class FundingScanner:
    FUNDING_EPOCH_HOURS = 1

    def __init__(self, client: PacificaClient, min_apy: float = 5.0):
        self.client = client
        self.min_apy = min_apy
        self._history_cache: dict[str, FundingHistory] = {}

    @staticmethod
    def rate_to_apy(hourly_rate: float) -> float:
        return hourly_rate * 365 * 24 * 100

    @staticmethod
    def rate_to_apy_8h(rate_8h: float) -> float:
        return rate_8h * 365 * 3 * 100

    async def fetch_all_funding_rates(self) -> list[dict]:
        prices = await self.client.get_prices()
        markets = await self.client.get_market_info()
        leverage_map = {m.symbol: m.max_leverage for m in markets}

        results = []
        for p in prices:
            results.append({
                "symbol": p.symbol,
                "funding_rate": sf(p.funding),
                "next_funding_rate": sf(p.next_funding),
                "mark_price": sf(p.mark),
                "oracle_price": sf(p.oracle),
                "open_interest": sf(p.open_interest),
                "volume_24h": sf(p.volume_24h),
                "max_leverage": leverage_map.get(p.symbol, 1),
            })
        return results

    def rank_by_funding_rate(self, rates: list[dict]) -> list[dict]:
        return sorted(rates, key=lambda x: abs(x["funding_rate"]), reverse=True)

    async def track_funding_history(self, symbol: str, limit: int = 168) -> FundingHistory:
        resp = await self.client.get_market_funding_history(symbol, limit=limit)
        records = resp.get("data", []) if isinstance(resp, dict) else []
        if not records:
            return FundingHistory(symbol=symbol)

        now_ms = int(time.time() * 1000)
        ms_24h = 24 * 3600 * 1000
        ms_7d = 7 * 24 * 3600 * 1000

        rates_24h = [sf(r.get("funding_rate")) for r in records if now_ms - r.get("created_at", 0) <= ms_24h]
        rates_7d = [sf(r.get("funding_rate")) for r in records if now_ms - r.get("created_at", 0) <= ms_7d]
        all_rates = [sf(r.get("funding_rate")) for r in records]

        positive_count = sum(1 for r in all_rates if r > 0)

        history = FundingHistory(
            symbol=symbol,
            rates=[{"rate": sf(r.get("funding_rate")), "timestamp": r.get("created_at", 0)} for r in records],
            avg_rate_24h=sum(rates_24h) / len(rates_24h) if rates_24h else 0.0,
            avg_rate_7d=sum(rates_7d) / len(rates_7d) if rates_7d else 0.0,
            positive_rate_pct=(positive_count / len(all_rates) * 100) if all_rates else 0.0,
        )
        self._history_cache[symbol] = history
        return history

    def _determine_trend(self, symbol: str) -> str:
        history = self._history_cache.get(symbol)
        if not history or len(history.rates) < 6:
            return "stable"

        recent = [r["rate"] for r in history.rates[:6]]
        older = [r["rate"] for r in history.rates[6:12]] if len(history.rates) >= 12 else recent

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)
        diff = avg_recent - avg_older

        if diff > 0.00005:
            return "rising"
        elif diff < -0.00005:
            return "falling"
        return "stable"

    async def scan(self, fetch_history: bool = True, max_history_fetches: int = 15) -> list[FundingOpportunity]:
        all_rates = await self.fetch_all_funding_rates()
        ranked = self.rank_by_funding_rate(all_rates)

        opportunities = []
        history_fetched = 0
        for r in ranked:
            apy_current = self.rate_to_apy(r["funding_rate"])
            apy_next = self.rate_to_apy(r["next_funding_rate"])

            if abs(apy_current) < self.min_apy:
                continue

            trend = "stable"
            if fetch_history and history_fetched < max_history_fetches:
                try:
                    await self.track_funding_history(r["symbol"], limit=24)
                    history_fetched += 1
                    await asyncio.sleep(0.15)
                except Exception:
                    pass
                trend = self._determine_trend(r["symbol"])

            opportunities.append(FundingOpportunity(
                symbol=r["symbol"],
                funding_rate=r["funding_rate"],
                next_funding_rate=r["next_funding_rate"],
                apy_current=apy_current,
                apy_next=apy_next,
                mark_price=r["mark_price"],
                oracle_price=r["oracle_price"],
                open_interest=r["open_interest"],
                volume_24h=r["volume_24h"],
                max_leverage=r["max_leverage"],
                trend=trend,
            ))

        return opportunities

    async def get_top_opportunities(self, n: int = 5) -> list[FundingOpportunity]:
        opps = await self.scan(fetch_history=True, max_history_fetches=n + 3)
        positive = [o for o in opps if o.funding_rate > 0]
        return sorted(positive, key=lambda x: x.apy_current, reverse=True)[:n]

    async def summary(self) -> dict:
        all_rates = await self.fetch_all_funding_rates()
        positive_rates = [r for r in all_rates if r["funding_rate"] > 0]
        positive_rates.sort(key=lambda x: abs(x["funding_rate"]), reverse=True)
        top_symbols = positive_rates[:8]

        top_opps = []
        for r in top_symbols:
            apy = self.rate_to_apy(r["funding_rate"])
            if abs(apy) < self.min_apy:
                continue
            trend = "stable"
            try:
                await self.track_funding_history(r["symbol"], limit=24)
                trend = self._determine_trend(r["symbol"])
                await asyncio.sleep(0.1)
            except Exception:
                pass
            top_opps.append({
                "symbol": r["symbol"],
                "funding_rate": f"{r['funding_rate']:.6f}",
                "apy": f"{apy:.2f}%",
                "trend": trend,
                "volume_24h": f"${r['volume_24h']:,.0f}",
            })

        above_threshold = sum(
            1 for r in all_rates if abs(self.rate_to_apy(r["funding_rate"])) >= self.min_apy
        )
        return {
            "total_pairs_scanned": len(all_rates),
            "opportunities_above_threshold": above_threshold,
            "top_5": top_opps[:5],
        }
