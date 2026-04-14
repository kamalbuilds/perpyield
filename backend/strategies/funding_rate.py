from __future__ import annotations

from pacifica.client import PacificaClient, sf

FUNDING_EPOCHS_PER_YEAR = 365 * 24


def _annualized_yield(funding_rate: float, epochs_per_year: int = FUNDING_EPOCHS_PER_YEAR) -> float:
    return funding_rate * epochs_per_year * 100


class FundingRateStrategy:
    def __init__(
        self,
        client: PacificaClient,
        symbols: list[str],
        min_annualized_yield_pct: float = 5.0,
    ):
        self.client = client
        self.symbols = symbols
        self.min_annualized_yield_pct = min_annualized_yield_pct

    @staticmethod
    def calculate_annualized_yield(
        funding_rate: float | str, funding_interval_hours: int = 1
    ) -> float:
        rate = sf(funding_rate)
        epochs_per_year = int(365 * 24 / funding_interval_hours)
        return _annualized_yield(rate, epochs_per_year)

    async def scan_opportunities(self) -> list[dict]:
        prices = await self.client.get_prices()
        markets = await self.client.get_markets()

        leverage_map: dict[str, int] = {}
        for m in markets:
            leverage_map[m.symbol] = m.max_leverage

        results = []
        for item in prices:
            sym = item.symbol
            if not sym:
                continue
            if self.symbols and sym not in self.symbols:
                continue

            funding_rate = sf(item.funding)
            next_funding = sf(item.next_funding)
            ann_yield = self.calculate_annualized_yield(funding_rate)

            if abs(ann_yield) < self.min_annualized_yield_pct:
                continue

            results.append({
                "symbol": sym,
                "funding_rate": funding_rate,
                "next_funding_rate": next_funding,
                "annualized_yield": round(ann_yield, 4),
                "direction": "short" if funding_rate > 0 else "long",
                "mark_price": sf(item.mark),
                "oracle_price": sf(item.oracle),
                "open_interest": sf(item.open_interest),
                "volume_24h": sf(item.volume_24h),
                "max_leverage": leverage_map.get(sym, 1),
            })

        return sorted(results, key=lambda x: abs(x["annualized_yield"]), reverse=True)

    async def get_strategy_signals(self) -> list[dict]:
        opportunities = await self.scan_opportunities()
        return [
            {
                "symbol": o["symbol"],
                "funding_rate": o["funding_rate"],
                "annualized_yield": o["annualized_yield"],
                "direction": o["direction"],
                "mark_price": o["mark_price"],
                "open_interest": o["open_interest"],
            }
            for o in opportunities
        ]
