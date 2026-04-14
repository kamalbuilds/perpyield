import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from pacifica.client import PacificaClient, sf
from strategy.funding_scanner import FundingScanner, FundingOpportunity

logger = logging.getLogger(__name__)


@dataclass
class PositionPair:
    symbol: str
    side: str
    size: float
    entry_price: float
    entry_funding_rate: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    cumulative_funding: float = 0.0
    cumulative_fees: float = 0.0


@dataclass
class StrategyConfig:
    min_funding_rate: float = 0.0001
    min_apy: float = 8.0
    max_leverage: float = 3.0
    max_position_pct: float = 0.25
    exit_funding_threshold: float = 0.00002
    slippage_tolerance: str = "0.5"
    max_open_positions: int = 5


class DeltaNeutralStrategy:
    def __init__(self, client: PacificaClient, config: Optional[StrategyConfig] = None):
        self.client = client
        self.config = config or StrategyConfig()
        self.scanner = FundingScanner(client, min_apy=self.config.min_apy)
        self.active_positions: dict[str, PositionPair] = {}

    async def find_opportunities(self) -> list[FundingOpportunity]:
        if not self.client.public_key:
            return []
        opps = await self.scanner.get_top_opportunities(n=10)
        filtered = []
        for opp in opps:
            if opp.symbol in self.active_positions:
                continue
            if opp.funding_rate < self.config.min_funding_rate:
                continue
            if opp.volume_24h < 50_000:
                continue
            if opp.trend == "falling":
                continue
            filtered.append(opp)
        return filtered

    async def calculate_position_size(self, opportunity: FundingOpportunity) -> float:
        account = await self.client.get_account()
        available = sf(account.available_to_spend)
        if available <= 0:
            return 0.0
        max_notional = available * self.config.max_position_pct
        leveraged_notional = max_notional * min(self.config.max_leverage, opportunity.max_leverage)
        return leveraged_notional / opportunity.mark_price

    async def should_enter(self, opportunity: FundingOpportunity) -> bool:
        if opportunity.funding_rate < self.config.min_funding_rate:
            return False
        if opportunity.apy_current < self.config.min_apy:
            return False
        if len(self.active_positions) >= self.config.max_open_positions:
            return False
        if opportunity.volume_24h < 50_000:
            return False

        history = await self.scanner.track_funding_history(opportunity.symbol, limit=24)
        if history.positive_rate_pct < 70:
            return False
        if history.avg_rate_24h < self.config.min_funding_rate * 0.5:
            return False

        return True

    async def should_exit(self, symbol: str) -> bool:
        if symbol not in self.active_positions:
            return False

        prices = await self.client.get_prices()
        current = next((p for p in prices if p.symbol == symbol), None)
        if not current:
            return True

        current_rate = sf(current.funding)
        next_rate = sf(current.next_funding)

        if current_rate < 0:
            logger.info(f"{symbol}: funding flipped negative ({current_rate}), exiting")
            return True

        if current_rate < self.config.exit_funding_threshold and next_rate < self.config.exit_funding_threshold:
            logger.info(f"{symbol}: funding below exit threshold, exiting")
            return True

        return False

    async def enter_position(self, opportunity: FundingOpportunity) -> Optional[PositionPair]:
        if not await self.should_enter(opportunity):
            logger.info(f"Skipping {opportunity.symbol}: entry conditions not met")
            return None

        size = await self.calculate_position_size(opportunity)
        if size <= 0:
            logger.warning(f"Insufficient balance for {opportunity.symbol}")
            return None

        amount_str = f"{size:.6f}"
        order_ids = []

        try:
            short_result = await self.client.create_market_order(
                symbol=opportunity.symbol,
                side="ask",
                amount=amount_str,
                slippage_percent=self.config.slippage_tolerance,
            )
            order_ids.append(short_result.get("order_id"))
            logger.info(f"Opened short {opportunity.symbol}: {amount_str} units")
        except Exception as e:
            logger.error(f"Failed to open short for {opportunity.symbol}: {e}")
            return None

        position = PositionPair(
            symbol=opportunity.symbol,
            side="short",
            size=size,
            entry_price=opportunity.mark_price,
            entry_funding_rate=opportunity.funding_rate,
            entry_time=int(time.time() * 1000),
            order_ids=order_ids,
        )
        self.active_positions[opportunity.symbol] = position
        return position

    async def exit_position(self, symbol: str) -> bool:
        pos = self.active_positions.get(symbol)
        if not pos:
            logger.warning(f"No active position for {symbol}")
            return False

        amount_str = f"{pos.size:.6f}"

        try:
            close_side = "bid" if pos.side == "short" else "ask"
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent=self.config.slippage_tolerance,
                reduce_only=True,
            )
            logger.info(f"Closed {pos.side} {symbol}: {amount_str} units")
        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return False

        del self.active_positions[symbol]
        return True

    async def update_position_funding(self, symbol: str):
        pos = self.active_positions.get(symbol)
        if not pos:
            return
        positions = await self.client.get_positions()
        live = next((p for p in positions if p.symbol == symbol), None)
        if live:
            pos.cumulative_funding = sf(live.funding)

    async def run_cycle(self) -> dict:
        actions = {"entered": [], "exited": [], "held": [], "errors": []}

        for symbol in list(self.active_positions.keys()):
            try:
                if await self.should_exit(symbol):
                    if await self.exit_position(symbol):
                        actions["exited"].append(symbol)
                    else:
                        actions["errors"].append(f"Failed to exit {symbol}")
                else:
                    await self.update_position_funding(symbol)
                    actions["held"].append(symbol)
            except Exception as e:
                actions["errors"].append(f"{symbol}: {e}")

        try:
            opportunities = await self.find_opportunities()
            for opp in opportunities:
                if len(self.active_positions) >= self.config.max_open_positions:
                    break
                pos = await self.enter_position(opp)
                if pos:
                    actions["entered"].append({
                        "symbol": pos.symbol,
                        "size": pos.size,
                        "funding_rate": pos.entry_funding_rate,
                        "apy": FundingScanner.rate_to_apy(pos.entry_funding_rate),
                    })
        except Exception as e:
            actions["errors"].append(f"Scan error: {e}")

        return actions

    def get_status(self) -> dict:
        total_funding = sum(p.cumulative_funding for p in self.active_positions.values())
        return {
            "active_positions": len(self.active_positions),
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "entry_funding_rate": p.entry_funding_rate,
                    "cumulative_funding": p.cumulative_funding,
                    "held_since": p.entry_time,
                }
                for p in self.active_positions.values()
            ],
            "total_funding_earned": total_funding,
        }
