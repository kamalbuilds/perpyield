import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from pacifica.client import PacificaClient, sf
from strategy.vault_manager import STRATEGY_REGISTRY, get_strategy_class

logger = logging.getLogger(__name__)


@dataclass
class PortfolioConfig:
    allocations: dict[str, float] = field(default_factory=lambda: {"delta_neutral": 0.4, "momentum_swing": 0.3, "mean_reversion": 0.3})
    rebalance_threshold: float = 0.05
    rebalance_interval_seconds: float = 3600.0

    def validate(self) -> list[str]:
        errors = []
        for sid, pct in self.allocations.items():
            if sid not in STRATEGY_REGISTRY:
                errors.append(f"Unknown strategy: {sid}")
            if pct < 0 or pct > 1:
                errors.append(f"Allocation for {sid} must be between 0 and 1, got {pct}")
        total = sum(self.allocations.values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"Allocations must sum to ~1.0, got {total:.4f}")
        return errors


@dataclass
class StrategyPerformance:
    strategy_id: str
    allocated_pct: float = 0.0
    current_pct: float = 0.0
    allocated_value: float = 0.0
    current_value: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    active_positions: int = 0
    last_cycle_result: Optional[dict] = None
    last_cycle_time: int = 0


class PortfolioManager:
    def __init__(
        self,
        client: PacificaClient,
        config: PortfolioConfig,
        total_capital: float = 0.0,
    ):
        self.client = client
        self.config = config
        self.total_capital = total_capital
        self.strategies: dict = {}
        self.performances: dict[str, StrategyPerformance] = {}
        self.last_rebalance_time: int = 0
        self.combined_pnl_history: list[dict] = []

        for strategy_id, pct in config.allocations.items():
            strategy_class, config_class = get_strategy_class(strategy_id)
            if strategy_class is None:
                logger.warning(f"Skipping unknown strategy {strategy_id} in portfolio")
                continue
            default_config = config_class()
            self.strategies[strategy_id] = strategy_class(client, default_config)
            self.performances[strategy_id] = StrategyPerformance(
                strategy_id=strategy_id,
                allocated_pct=pct,
            )

    async def run_cycle(self) -> dict:
        results = {}
        for strategy_id, strategy in self.strategies.items():
            try:
                cycle_result = await strategy.run_cycle()
                results[strategy_id] = cycle_result
                perf = self.performances[strategy_id]
                perf.last_cycle_result = cycle_result
                perf.last_cycle_time = int(time.time() * 1000)
                perf.active_positions = len(getattr(strategy, 'active_positions', {}))
            except Exception as e:
                logger.error(f"Portfolio cycle error for {strategy_id}: {e}")
                results[strategy_id] = {"errors": [str(e)]}

        await self._update_performances()
        return results

    async def _update_performances(self):
        vault_value = await self._estimate_total_value()

        for strategy_id, strategy in self.strategies.items():
            perf = self.performances[strategy_id]
            perf.allocated_value = vault_value * perf.allocated_pct
            perf.current_value = self._estimate_strategy_value(strategy_id, strategy, vault_value)

            if vault_value > 0:
                perf.current_pct = perf.current_value / vault_value
            else:
                perf.current_pct = perf.allocated_pct

            if perf.allocated_value > 0:
                perf.pnl = perf.current_value - perf.allocated_value
                perf.pnl_pct = (perf.pnl / perf.allocated_value) * 100
            else:
                perf.pnl = 0.0
                perf.pnl_pct = 0.0

    async def _estimate_total_value(self) -> float:
        if not self.client.public_key:
            return self.total_capital
        try:
            account = await self.client.get_account()
            return sf(account.equity) if hasattr(account, 'equity') else self.total_capital
        except Exception:
            return self.total_capital

    def _estimate_strategy_value(self, strategy_id: str, strategy, vault_value: float) -> float:
        allocated = vault_value * self.config.allocations.get(strategy_id, 0)
        positions = getattr(strategy, 'active_positions', {})

        unrealized_pnl = 0.0
        for symbol, pos in positions.items():
            entry_price = getattr(pos, 'entry_price', 0)
            size = getattr(pos, 'size', 0)
            side = getattr(pos, 'side', '')
            direction = getattr(pos, 'direction', None)

            if direction is not None:
                dir_val = str(direction).lower()
                is_long = 'bullish' in dir_val or 'long' in dir_val or 'oversold' in dir_val
            else:
                is_long = side == 'long'

            cumulative = getattr(pos, 'cumulative_funding', 0.0)
            unrealized_pnl += cumulative

        return allocated + unrealized_pnl

    async def get_combined_pnl(self) -> dict:
        await self._update_performances()

        total_pnl = sum(p.pnl for p in self.performances.values())
        total_value = sum(p.current_value for p in self.performances.values())
        total_allocated = sum(p.allocated_value for p in self.performances.values())

        combined_pct = (total_pnl / total_allocated * 100) if total_allocated > 0 else 0.0

        entry = {
            "timestamp": int(time.time() * 1000),
            "combined_pnl": total_pnl,
            "combined_pct": combined_pct,
            "total_value": total_value,
        }
        self.combined_pnl_history.append(entry)
        self.combined_pnl_history = self.combined_pnl_history[-200:]

        return {
            "combined_pnl": total_pnl,
            "combined_pnl_pct": combined_pct,
            "total_value": total_value,
            "total_allocated": total_allocated,
            "strategy_breakdown": {
                sid: {
                    "strategy_id": perf.strategy_id,
                    "allocated_pct": round(perf.allocated_pct, 4),
                    "current_pct": round(perf.current_pct, 4),
                    "allocated_value": round(perf.allocated_value, 2),
                    "current_value": round(perf.current_value, 2),
                    "pnl": round(perf.pnl, 2),
                    "pnl_pct": round(perf.pnl_pct, 2),
                    "active_positions": perf.active_positions,
                    "drift": round(abs(perf.current_pct - perf.allocated_pct), 4),
                }
                for sid, perf in self.performances.items()
            },
        }

    async def get_drift_report(self) -> dict:
        await self._update_performances()
        drifts = {}
        needs_rebalance = False

        for sid, perf in self.performances.items():
            drift = abs(perf.current_pct - perf.allocated_pct)
            drifts[sid] = {
                "strategy_id": sid,
                "target_pct": round(perf.allocated_pct, 4),
                "actual_pct": round(perf.current_pct, 4),
                "drift": round(drift, 4),
                "needs_rebalance": drift > self.config.rebalance_threshold,
            }
            if drift > self.config.rebalance_threshold:
                needs_rebalance = True

        return {
            "needs_rebalance": needs_rebalance,
            "threshold": self.config.rebalance_threshold,
            "drifts": drifts,
        }

    async def rebalance(self) -> dict:
        drift_report = await self.get_drift_report()
        if not drift_report["needs_rebalance"]:
            return {"status": "no_rebalance_needed", "drifts": drift_report["drifts"]}

        adjustments = []
        vault_value = await self._estimate_total_value()

        for sid, perf in self.performances.items():
            drift = abs(perf.current_pct - perf.allocated_pct)
            if drift <= self.config.rebalance_threshold:
                continue

            strategy = self.strategies.get(sid)
            if not strategy:
                continue

            positions = getattr(strategy, 'active_positions', {})
            target_value = vault_value * perf.allocated_pct
            current_value = perf.current_value
            diff = target_value - current_value

            if current_value == 0 and target_value > 0:
                adjustments.append({
                    "strategy_id": sid,
                    "action": "allocate",
                    "target_value": round(target_value, 2),
                    "diff": round(diff, 2),
                })
            elif target_value == 0 and current_value > 0:
                adjustments.append({
                    "strategy_id": sid,
                    "action": "close_all",
                    "current_value": round(current_value, 2),
                    "positions_to_close": list(positions.keys()),
                })
                for symbol in list(positions.keys()):
                    try:
                        if hasattr(strategy, 'exit_position'):
                            exit_args = [symbol]
                            from strategy.mean_reversion import MeanReversionStrategy
                            from strategy.volatility_breakout import VolatilityBreakoutStrategy
                            if isinstance(strategy, (MeanReversionStrategy, VolatilityBreakoutStrategy)):
                                exit_args.append("rebalance")
                            await strategy.exit_position(*exit_args)
                        elif hasattr(strategy, 'active_positions'):
                            pos = positions[symbol]
                            side = getattr(pos, 'side', '')
                            direction = getattr(pos, 'direction', None)
                            if direction is not None:
                                dir_val = str(direction).lower()
                                close_side = "bid" if ('bearish' in dir_val or 'short' in dir_val or 'overbought' in dir_val) else "ask"
                            else:
                                close_side = "bid" if side == "short" else "ask"
                            await self.client.create_market_order(
                                symbol=symbol,
                                side=close_side,
                                amount=f"{getattr(pos, 'size', 0):.6f}",
                                slippage_percent="0.5",
                                reduce_only=True,
                            )
                            del positions[symbol]
                    except Exception as e:
                        logger.error(f"Rebalance close failed for {sid}/{symbol}: {e}")
            else:
                if diff > 0:
                    adjustments.append({
                        "strategy_id": sid,
                        "action": "scale_up",
                        "target_value": round(target_value, 2),
                        "diff": round(diff, 2),
                    })
                else:
                    fraction_to_reduce = abs(diff) / current_value if current_value > 0 else 0
                    adjustments.append({
                        "strategy_id": sid,
                        "action": "scale_down",
                        "target_value": round(target_value, 2),
                        "diff": round(diff, 2),
                        "fraction_to_reduce": round(fraction_to_reduce, 4),
                    })

        self.last_rebalance_time = int(time.time() * 1000)
        await self._update_performances()

        return {
            "status": "rebalanced",
            "adjustments": adjustments,
            "new_allocations": {
                sid: round(perf.current_pct, 4)
                for sid, perf in self.performances.items()
            },
        }

    def update_allocations(self, new_allocations: dict[str, float]) -> list[str]:
        errors = []
        for sid in new_allocations:
            if sid not in STRATEGY_REGISTRY:
                errors.append(f"Unknown strategy: {sid}")

        total = sum(new_allocations.values())
        if abs(total - 1.0) > 0.01:
            errors.append(f"Allocations must sum to ~1.0, got {total:.4f}")

        if errors:
            return errors

        for sid, pct in new_allocations.items():
            self.config.allocations[sid] = pct
            if sid in self.performances:
                self.performances[sid].allocated_pct = pct

            if sid not in self.strategies:
                strategy_class, config_class = get_strategy_class(sid)
                if strategy_class:
                    self.strategies[sid] = strategy_class(self.client, config_class())
                    self.performances[sid] = StrategyPerformance(
                        strategy_id=sid,
                        allocated_pct=pct,
                    )

        for sid in list(self.strategies.keys()):
            if sid not in new_allocations:
                del self.strategies[sid]
                if sid in self.performances:
                    del self.performances[sid]

        return []

    def get_status(self) -> dict:
        return {
            "portfolio_mode": True,
            "allocations": self.config.allocations,
            "rebalance_threshold": self.config.rebalance_threshold,
            "last_rebalance_time": self.last_rebalance_time,
            "strategy_count": len(self.strategies),
            "strategies": {
                sid: {
                    "allocated_pct": perf.allocated_pct,
                    "current_pct": perf.current_pct,
                    "pnl": perf.pnl,
                    "pnl_pct": perf.pnl_pct,
                    "active_positions": perf.active_positions,
                }
                for sid, perf in self.performances.items()
            },
        }
