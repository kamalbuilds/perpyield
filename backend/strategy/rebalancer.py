import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Optional

from pacifica.client import PacificaClient, sf

logger = logging.getLogger(__name__)


@dataclass
class RebalanceConfig:
    delta_threshold_pct: float = 5.0
    check_interval_seconds: int = 300
    slippage_tolerance: str = "0.5"
    min_rebalance_size_usd: float = 10.0


@dataclass
class DeltaReport:
    symbol: str
    long_notional: float
    short_notional: float
    net_delta: float
    total_notional: float
    delta_pct: float
    needs_rebalance: bool


class Rebalancer:
    def __init__(self, client: PacificaClient, config: Optional[RebalanceConfig] = None):
        self.client = client
        self.config = config or RebalanceConfig()
        self.last_check_time: int = 0
        self.rebalance_history: list[dict] = []
        self._running = False

    async def calculate_delta(self) -> list[DeltaReport]:
        try:
            positions = await self.client.get_positions()
        except RuntimeError:
            return []
        prices = await self.client.get_prices()
        price_map = {p.symbol: sf(p.mark) for p in prices}

        symbol_groups: dict[str, list] = {}
        for pos in positions:
            symbol_groups.setdefault(pos.symbol, []).append(pos)

        reports = []
        for symbol, pos_list in symbol_groups.items():
            mark = price_map.get(symbol, 0)
            if mark == 0:
                continue

            long_notional = 0.0
            short_notional = 0.0
            for pos in pos_list:
                amount = abs(sf(pos.amount))
                notional = amount * mark
                if pos.side == "long" or sf(pos.amount) > 0:
                    long_notional += notional
                else:
                    short_notional += notional

            net_delta = long_notional - short_notional
            total_notional = long_notional + short_notional
            delta_pct = (abs(net_delta) / total_notional * 100) if total_notional > 0 else 0.0

            reports.append(DeltaReport(
                symbol=symbol,
                long_notional=long_notional,
                short_notional=short_notional,
                net_delta=net_delta,
                total_notional=total_notional,
                delta_pct=delta_pct,
                needs_rebalance=delta_pct > self.config.delta_threshold_pct,
            ))

        return reports

    def needs_rebalance(self, report: DeltaReport) -> bool:
        return report.needs_rebalance

    async def rebalance(self, report: DeltaReport) -> Optional[dict]:
        if not self.needs_rebalance(report):
            return None

        prices = await self.client.get_prices()
        price_entry = next((p for p in prices if p.symbol == report.symbol), None)
        if not price_entry:
            logger.error(f"No price data for {report.symbol}")
            return None

        mark = sf(price_entry.mark)
        if mark == 0:
            return None

        adjustment_notional = abs(report.net_delta) / 2
        if adjustment_notional < self.config.min_rebalance_size_usd:
            logger.info(f"{report.symbol}: delta drift ${adjustment_notional:.2f} below min rebalance size")
            return None

        adjustment_size = adjustment_notional / mark

        if report.net_delta > 0:
            side = "ask"
            action = "increase_short"
        else:
            side = "bid"
            action = "increase_long"

        try:
            result = await self.client.create_market_order(
                symbol=report.symbol,
                side=side,
                amount=f"{adjustment_size:.6f}",
                slippage_percent=self.config.slippage_tolerance,
            )

            record = {
                "timestamp": int(time.time() * 1000),
                "symbol": report.symbol,
                "action": action,
                "adjustment_size": adjustment_size,
                "adjustment_notional": adjustment_notional,
                "delta_before": report.net_delta,
                "delta_pct_before": report.delta_pct,
                "order_id": result.get("order_id"),
            }
            self.rebalance_history.append(record)
            logger.info(
                f"Rebalanced {report.symbol}: {action} {adjustment_size:.6f} "
                f"(delta was {report.delta_pct:.1f}%)"
            )
            return record

        except Exception as e:
            logger.error(f"Rebalance failed for {report.symbol}: {e}")
            return None

    async def run_check(self) -> list[dict]:
        now = int(time.time())
        if now - self.last_check_time < self.config.check_interval_seconds:
            return []

        self.last_check_time = now
        reports = await self.calculate_delta()
        results = []

        for report in reports:
            if self.needs_rebalance(report):
                logger.info(
                    f"{report.symbol}: delta {report.delta_pct:.1f}% exceeds "
                    f"{self.config.delta_threshold_pct}% threshold"
                )
                result = await self.rebalance(report)
                if result:
                    results.append(result)

        return results

    async def run_loop(self, interval: int = 300) -> None:
        self._running = True
        logger.info(f"Rebalancer loop started, interval={interval}s")
        while self._running:
            try:
                results = await self.run_check()
                if results:
                    logger.info(f"Rebalancer executed {len(results)} adjustments")
            except Exception as e:
                logger.error(f"Rebalancer loop error: {e}")
            await asyncio.sleep(interval)
        logger.info("Rebalancer loop stopped")

    def stop_loop(self) -> None:
        self._running = False

    async def get_delta_summary(self) -> dict:
        reports = await self.calculate_delta()
        return {
            "positions_tracked": len(reports),
            "positions_needing_rebalance": sum(1 for r in reports if r.needs_rebalance),
            "total_rebalances_executed": len(self.rebalance_history),
            "positions": [
                {
                    "symbol": r.symbol,
                    "long_notional": f"${r.long_notional:,.2f}",
                    "short_notional": f"${r.short_notional:,.2f}",
                    "net_delta": f"${r.net_delta:,.2f}",
                    "delta_pct": f"{r.delta_pct:.2f}%",
                    "needs_rebalance": r.needs_rebalance,
                }
                for r in reports
            ],
        }
