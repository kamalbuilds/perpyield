import json
import time
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Type

from pacifica.client import PacificaClient, sf
from strategy.delta_neutral import DeltaNeutralStrategy, StrategyConfig
from strategy.momentum_swing import MomentumSwingStrategy, MomentumConfig
from strategy.mean_reversion import MeanReversionStrategy, MeanReversionConfig
from strategy.volatility_breakout import VolatilityBreakoutStrategy, VolatilityBreakoutConfig
from strategy.rebalancer import Rebalancer, RebalanceConfig
from strategy.portfolio_manager import PortfolioManager, PortfolioConfig
from strategy.risk_manager import RiskManager, RiskConfig, RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class FeeConfig:
    management_fee_annual: float = 0.005
    performance_fee: float = 0.10
    protocol_fee: float = 0.005
    creator_address: Optional[str] = None
    high_water_mark: float = 0.0
    last_fee_charge_time: int = 0


@dataclass
class FeeAccrual:
    creator_management_fees_earned: float = 0.0
    creator_performance_fees_earned: float = 0.0
    protocol_fees_earned: float = 0.0
    creator_fees_withdrawn: float = 0.0
    protocol_fees_withdrawn: float = 0.0
    fee_charge_history: list = field(default_factory=list)


# Strategy Registry - Maps strategy IDs to their classes and configs
STRATEGY_REGISTRY = {
    "delta_neutral": {
        "name": "Delta Neutral (Funding Arbitrage)",
        "class": DeltaNeutralStrategy,
        "config_class": StrategyConfig,
        "description": "Earn funding rate payments by shorting high-funding assets",
        "indicators": ["Funding Rate", "Funding History"],
        "risk_level": "Low",
        "expected_apy": "5-20%",
    },
    "momentum_swing": {
        "name": "Momentum Swing",
        "class": MomentumSwingStrategy,
        "config_class": MomentumConfig,
        "description": "Trend-following strategy using EMA crossover + RSI + MACD",
        "indicators": ["EMA", "RSI", "MACD"],
        "risk_level": "Medium",
        "expected_apy": "15-50%",
    },
    "mean_reversion": {
        "name": "Mean Reversion",
        "class": MeanReversionStrategy,
        "config_class": MeanReversionConfig,
        "description": "Counter-trend strategy using Bollinger Bands + RSI",
        "indicators": ["Bollinger Bands", "RSI", "SMA"],
        "risk_level": "Medium",
        "expected_apy": "10-40%",
    },
    "volatility_breakout": {
        "name": "Volatility Breakout",
        "class": VolatilityBreakoutStrategy,
        "config_class": VolatilityBreakoutConfig,
        "description": "Breakout strategy using ATR + volume confirmation",
        "indicators": ["ATR", "Volume", "Support/Resistance"],
        "risk_level": "High",
        "expected_apy": "20-80%",
    },
}


def get_strategy_class(strategy_id: str):
    """Get strategy class by ID."""
    entry = STRATEGY_REGISTRY.get(strategy_id)
    if entry:
        return entry["class"], entry["config_class"]
    return None, None


def list_available_strategies() -> list[dict]:
    """List all available strategies for the marketplace."""
    return [
        {
            "id": sid,
            "name": data["name"],
            "description": data["description"],
            "indicators": data["indicators"],
            "risk_level": data["risk_level"],
            "expected_apy": data["expected_apy"],
        }
        for sid, data in STRATEGY_REGISTRY.items()
    ]


@dataclass
class Depositor:
    address: str
    shares: float
    deposited_amount: float
    deposit_time: int


@dataclass
class VaultSocialStats:
    clone_count: int = 0
    follower_count: int = 0
    view_count: int = 0
    weekly_depositors: int = 0
    created_at: int = 0


@dataclass
class VaultState:
    vault_id: str
    total_shares: float = 0.0
    total_deposited: float = 0.0
    total_funding_earned: float = 0.0
    total_fees_paid: float = 0.0
    depositors: dict[str, Depositor] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0
    is_active: bool = True
    strategy_id: str = "delta_neutral"
    strategy_config: dict = field(default_factory=dict)
    cloned_from: Optional[str] = None
    clone_count: int = 0
    creator_address: Optional[str] = None
    vault_name: Optional[str] = None
    description: Optional[str] = None
    performance_history: list = field(default_factory=list)
    social_stats: dict = field(default_factory=dict)
    portfolio_mode: bool = False
    portfolio_allocations: dict[str, float] = field(default_factory=dict)
    per_strategy_performance: dict[str, dict] = field(default_factory=dict)
    fee_config: dict = field(default_factory=lambda: {
        "management_fee_annual": 0.005,
        "performance_fee": 0.10,
        "protocol_fee": 0.005,
        "high_water_mark": 0.0,
        "last_fee_charge_time": 0,
    })
    fee_accrual: dict = field(default_factory=lambda: {
        "creator_management_fees_earned": 0.0,
        "creator_performance_fees_earned": 0.0,
        "protocol_fees_earned": 0.0,
        "creator_fees_withdrawn": 0.0,
        "protocol_fees_withdrawn": 0.0,
        "fee_charge_history": [],
    })


class VaultManager:
    """
    Multi-Strategy Vault Manager

    Supports multiple trading strategies:
    - delta_neutral: Funding rate arbitrage
    - momentum_swing: Trend following
    - mean_reversion: Bollinger Bands mean reversion
    - volatility_breakout: ATR-based breakout
    """

    def __init__(
        self,
        client: PacificaClient,
        vault_id: str = "perpyield-v1",
        state_dir: str = "data",
        strategy_config: Optional[StrategyConfig] = None,
        rebalance_config: Optional[RebalanceConfig] = None,
        risk_config: Optional[RiskConfig] = None,
    ):
        self.client = client
        self.vault_id = vault_id
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{vault_id}.json"
        self.rebalance_config = rebalance_config

        self.state = self._load_state()

        self.strategy = self._init_strategy()
        self.rebalancer = Rebalancer(client, rebalance_config)
        self.risk_manager = RiskManager(risk_config, state_dir=str(self.state_dir))

        self.portfolio_manager: Optional[PortfolioManager] = None
        if self.state.portfolio_mode and self.state.portfolio_allocations:
            portfolio_config = PortfolioConfig(allocations=self.state.portfolio_allocations)
            self.portfolio_manager = PortfolioManager(
                client, portfolio_config, total_capital=self.state.total_deposited
            )

        self._sync_risk_positions()

    def _init_strategy(self):
        """Initialize strategy based on vault's strategy_id."""
        strategy_id = self.state.strategy_id
        strategy_class, config_class = get_strategy_class(strategy_id)

        if strategy_class is None:
            logger.warning(f"Unknown strategy {strategy_id}, defaulting to delta_neutral")
            strategy_id = "delta_neutral"
            strategy_class, config_class = get_strategy_class(strategy_id)
            self.state.strategy_id = strategy_id

        # Load saved config or use defaults
        config_kwargs = self.state.strategy_config if self.state.strategy_config else {}
        config = config_class(**config_kwargs) if config_kwargs else config_class()

        logger.info(f"Initialized {strategy_id} strategy for vault {self.vault_id}")
        return strategy_class(self.client, config)

    def _sync_risk_positions(self):
        if hasattr(self.strategy, 'active_positions'):
            self.risk_manager.update_positions(self.strategy.active_positions)

    def _load_state(self) -> VaultState:
        if self.state_file.exists():
            raw = json.loads(self.state_file.read_text())
            depositors = {}
            for addr, dep in raw.get("depositors", {}).items():
                depositors[addr] = Depositor(**dep)
            return VaultState(
                vault_id=raw["vault_id"],
                total_shares=raw["total_shares"],
                total_deposited=raw["total_deposited"],
                total_funding_earned=raw.get("total_funding_earned", 0.0),
                total_fees_paid=raw.get("total_fees_paid", 0.0),
                depositors=depositors,
                created_at=raw["created_at"],
                updated_at=raw["updated_at"],
                is_active=raw.get("is_active", True),
                strategy_id=raw.get("strategy_id", "delta_neutral"),
                strategy_config=raw.get("strategy_config", {}),
                cloned_from=raw.get("cloned_from"),
                clone_count=raw.get("clone_count", 0),
                creator_address=raw.get("creator_address"),
                vault_name=raw.get("vault_name"),
                description=raw.get("description"),
                performance_history=raw.get("performance_history", []),
                social_stats=raw.get("social_stats", {}),
                portfolio_mode=raw.get("portfolio_mode", False),
                portfolio_allocations=raw.get("portfolio_allocations", {}),
                per_strategy_performance=raw.get("per_strategy_performance", {}),
                fee_config=raw.get("fee_config", {
                    "management_fee_annual": 0.005,
                    "performance_fee": 0.10,
                    "protocol_fee": 0.005,
                    "high_water_mark": 0.0,
                    "last_fee_charge_time": 0,
                }),
                fee_accrual=raw.get("fee_accrual", {
                    "creator_management_fees_earned": 0.0,
                    "creator_performance_fees_earned": 0.0,
                    "protocol_fees_earned": 0.0,
                    "creator_fees_withdrawn": 0.0,
                    "protocol_fees_withdrawn": 0.0,
                    "fee_charge_history": [],
                }),
            )
        return VaultState(vault_id=self.vault_id)

    def _save_state(self):
        self.state.updated_at = int(time.time() * 1000)
        data = {
            "vault_id": self.state.vault_id,
            "total_shares": self.state.total_shares,
            "total_deposited": self.state.total_deposited,
            "total_funding_earned": self.state.total_funding_earned,
            "total_fees_paid": self.state.total_fees_paid,
            "depositors": {addr: asdict(dep) for addr, dep in self.state.depositors.items()},
            "created_at": self.state.created_at,
            "updated_at": self.state.updated_at,
            "is_active": self.state.is_active,
            "strategy_id": self.state.strategy_id,
            "strategy_config": self.state.strategy_config,
            "cloned_from": self.state.cloned_from,
            "clone_count": self.state.clone_count,
            "creator_address": self.state.creator_address,
            "vault_name": self.state.vault_name,
            "description": self.state.description,
            "performance_history": self.state.performance_history[-100:],
            "social_stats": self.state.social_stats,
            "portfolio_mode": self.state.portfolio_mode,
            "portfolio_allocations": self.state.portfolio_allocations,
            "per_strategy_performance": self.state.per_strategy_performance,
            "fee_config": self.state.fee_config,
            "fee_accrual": self.state.fee_accrual,
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def create_vault(self, name: Optional[str] = None, description: Optional[str] = None, creator: Optional[str] = None) -> dict:
        if self.state.created_at > 0:
            return {"status": "already_exists", "vault_id": self.vault_id}
        self.state.created_at = int(time.time() * 1000)
        if name:
            self.state.vault_name = name
        if description:
            self.state.description = description
        if creator:
            self.state.creator_address = creator
        self._save_state()
        logger.info(f"Vault {self.vault_id} created with strategy {self.state.strategy_id}")
        return {
            "status": "created",
            "vault_id": self.vault_id,
            "strategy_id": self.state.strategy_id,
            "strategy_name": STRATEGY_REGISTRY[self.state.strategy_id]["name"],
            "created_at": self.state.created_at,
        }

    async def switch_strategy(self, strategy_id: str, config: Optional[dict] = None) -> dict:
        """Switch vault to a different strategy."""
        if strategy_id not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {strategy_id}. Available: {list(STRATEGY_REGISTRY.keys())}")

        # Close existing positions before switching
        if hasattr(self.strategy, 'active_positions') and self.strategy.active_positions:
            logger.info(f"Closing {len(self.strategy.active_positions)} positions before strategy switch")
            for symbol in list(self.strategy.active_positions.keys()):
                try:
                    await self._close_position(symbol)
                except Exception as e:
                    logger.error(f"Failed to close {symbol}: {e}")

        # Update state
        self.state.strategy_id = strategy_id
        self.state.strategy_config = config or {}

        # Reinitialize strategy
        self.strategy = self._init_strategy()
        self._save_state()

        logger.info(f"Switched vault {self.vault_id} to {strategy_id}")
        return {
            "status": "switched",
            "vault_id": self.vault_id,
            "strategy_id": strategy_id,
            "strategy_name": STRATEGY_REGISTRY[strategy_id]["name"],
        }

    def clone_vault(self, new_vault_id: str, cloner_address: str) -> dict:
        """Clone this vault's configuration to a new vault."""
        self.state.clone_count += 1
        self._save_state()

        # Return clone configuration
        return {
            "status": "clone_template_created",
            "template": {
                "vault_id": new_vault_id,
                "strategy_id": self.state.strategy_id,
                "strategy_config": self.state.strategy_config,
                "cloned_from": self.vault_id,
                "creator_address": cloner_address,
                "strategy_name": STRATEGY_REGISTRY[self.state.strategy_id]["name"],
            }
        }

    async def _close_position(self, symbol: str):
        """Close a position for strategy switch."""
        if hasattr(self.strategy, 'exit_position'):
            await self.strategy.exit_position(symbol)
        elif hasattr(self.strategy, 'active_positions'):
            pos = self.strategy.active_positions.get(symbol)
            if pos:
                side = "bid" if pos.side == "short" else "ask"
                await self.client.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=f"{pos.size:.6f}",
                    slippage_percent="0.5",
                    reduce_only=True,
                )

    async def get_total_vault_value(self) -> float:
        """
        Calculate vault value based on deposits and trading PnL.

        Instead of using total account equity (which includes non-vault funds),
        we calculate: vault_value = total_deposited + unrealized_pnl_from_positions

        This gives accurate share pricing for vault-specific performance.
        """
        if not self.client.public_key:
            return self.state.total_deposited

        # Start with total deposits
        base_value = self.state.total_deposited

        # Calculate unrealized PnL from active positions
        unrealized_pnl = 0.0

        if hasattr(self.strategy, 'active_positions'):
            try:
                positions = await self.client.get_positions()
                prices = await self.client.get_prices()
                price_map = {p.symbol: sf(p.mark) for p in prices}

                for symbol, pos in self.strategy.active_positions.items():
                    current_price = price_map.get(symbol, 0)
                    if current_price > 0 and hasattr(pos, 'entry_price'):
                        # Calculate PnL for this position
                        if hasattr(pos, 'side') or hasattr(pos, 'direction'):
                            # For strategies with direction/side
                            direction = 1 if (getattr(pos, 'side', '') == 'long' or
                                            str(getattr(pos, 'direction', '')).lower() == 'bullish') else -1

                            price_diff = (current_price - pos.entry_price) * direction
                            position_value = getattr(pos, 'size', 0) * pos.entry_price
                            position_pnl = getattr(pos, 'size', 0) * price_diff
                            unrealized_pnl += position_pnl
            except Exception as e:
                logger.warning(f"Could not calculate position PnL: {e}")

        # Add any accumulated funding earned
        realized_earnings = self.state.total_funding_earned - self.state.total_fees_paid

        vault_value = base_value + unrealized_pnl + realized_earnings

        # Ensure vault value doesn't go negative
        return max(0, vault_value)

    async def get_share_price(self) -> float:
        if self.state.total_shares <= 0:
            return 1.0
        vault_value = await self.get_total_vault_value()
        return vault_value / self.state.total_shares

    async def deposit(self, depositor_address: str, amount: float) -> dict:
        if not self.state.is_active:
            raise RuntimeError("Vault is not active")
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        share_price = await self.get_share_price()
        new_shares = amount / share_price

        if depositor_address in self.state.depositors:
            dep = self.state.depositors[depositor_address]
            dep.shares += new_shares
            dep.deposited_amount += amount
        else:
            self.state.depositors[depositor_address] = Depositor(
                address=depositor_address,
                shares=new_shares,
                deposited_amount=amount,
                deposit_time=int(time.time() * 1000),
            )

        self.state.total_shares += new_shares
        self.state.total_deposited += amount
        self._save_state()

        logger.info(f"Deposit: {depositor_address} deposited ${amount:.2f}, received {new_shares:.6f} shares")
        return {
            "depositor": depositor_address,
            "amount": amount,
            "shares_received": new_shares,
            "share_price": share_price,
            "total_shares": self.state.depositors[depositor_address].shares,
            "strategy_id": self.state.strategy_id,
            "strategy_name": STRATEGY_REGISTRY[self.state.strategy_id]["name"],
        }

    async def withdraw(self, depositor_address: str, shares_to_redeem: Optional[float] = None) -> dict:
        dep = self.state.depositors.get(depositor_address)
        if not dep:
            raise ValueError(f"No deposits found for {depositor_address}")

        if shares_to_redeem is None:
            shares_to_redeem = dep.shares

        if shares_to_redeem > dep.shares:
            raise ValueError(f"Insufficient shares: have {dep.shares}, requested {shares_to_redeem}")

        share_price = await self.get_share_price()
        withdrawal_amount = shares_to_redeem * share_price

        pct_of_vault = shares_to_redeem / self.state.total_shares if self.state.total_shares > 0 else 0
        if pct_of_vault > 0.1:
            await self._close_proportional_positions(pct_of_vault)

        dep.shares -= shares_to_redeem
        self.state.total_shares -= shares_to_redeem

        if dep.shares <= 0.000001:
            del self.state.depositors[depositor_address]

        self._save_state()

        logger.info(
            f"Withdrawal: {depositor_address} redeemed {shares_to_redeem:.6f} shares "
            f"for ${withdrawal_amount:.2f}"
        )
        return {
            "depositor": depositor_address,
            "shares_redeemed": shares_to_redeem,
            "amount_received": withdrawal_amount,
            "share_price": share_price,
            "remaining_shares": dep.shares if depositor_address in self.state.depositors else 0,
        }

    async def _close_proportional_positions(self, fraction: float):
        if hasattr(self.strategy, 'active_positions'):
            for symbol, pos in list(self.strategy.active_positions.items()):
                close_size = pos.size * fraction
                if close_size <= 0:
                    continue
                try:
                    if hasattr(pos, 'side'):
                        close_side = "bid" if pos.side == "short" else "ask"
                    elif hasattr(pos, 'direction'):
                        from strategy.momentum_swing import TrendDirection
                        close_side = "ask" if pos.direction == TrendDirection.BULLISH else "bid"
                    else:
                        continue

                    await self.client.create_market_order(
                        symbol=symbol,
                        side=close_side,
                        amount=f"{close_size:.6f}",
                        slippage_percent="0.5",
                        reduce_only=True,
                    )
                    pos.size -= close_size
                    logger.info(f"Closed {fraction*100:.1f}% of {symbol} position for withdrawal")
                except Exception as e:
                    logger.error(f"Failed to close proportional position {symbol}: {e}")

    async def calculate_pnl(self) -> dict:
        vault_value = await self.get_total_vault_value()
        total_deposited = self.state.total_deposited

        strategy_status = self.strategy.get_status()
        # Different strategies track different metrics
        if hasattr(strategy_status, 'total_funding_earned'):
            funding_earned = strategy_status.get("total_funding_earned", 0.0)
        else:
            funding_earned = 0.0

        net_pnl = vault_value - total_deposited
        pnl_pct = (net_pnl / total_deposited * 100) if total_deposited > 0 else 0.0

        age_hours = 0.0
        if self.state.created_at > 0:
            age_hours = (time.time() * 1000 - self.state.created_at) / (3600 * 1000)
        annualized_return = (pnl_pct / age_hours * 8760) if age_hours > 1 else 0.0

        self.state.total_funding_earned = funding_earned

        # Record performance history
        self.state.performance_history.append({
            "timestamp": int(time.time() * 1000),
            "vault_value": vault_value,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
        })

        self._save_state()

        share_price = await self.get_share_price()
        return {
            "vault_value": vault_value,
            "total_deposited": total_deposited,
            "net_pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "funding_earned": funding_earned,
            "fees_paid": self.state.total_fees_paid,
            "annualized_return": annualized_return,
            "share_price": share_price,
            "total_shares": self.state.total_shares,
            "depositor_count": len(self.state.depositors),
            "age_hours": age_hours,
        }

    async def run_strategy_cycle(self) -> dict:
        """Run one strategy cycle with risk management."""
        self._sync_risk_positions()
        risk_status = await self.risk_manager.check_risk_limits(self.state)

        if risk_status.level == RiskLevel.VIOLATION:
            logger.warning(f"Risk violation detected, skipping strategy cycle: {risk_status.violations}")

        if self.risk_manager.emergency_stop_active:
            logger.critical("Emergency stop active, halting all trading")
            return {
                "strategy": {"entered": [], "exited": [], "held": [], "errors": ["Emergency stop active"]},
                "strategy_id": self.state.strategy_id,
                "strategy_name": STRATEGY_REGISTRY[self.state.strategy_id]["name"],
                "risk_status": {"level": risk_status.level.value, "violations": risk_status.violations, "circuit_breaker": risk_status.circuit_breaker_active, "emergency_stop": True},
                "pnl": await self.calculate_pnl(),
                "timestamp": int(time.time() * 1000),
            }

        if self.risk_manager.circuit_breaker_active:
            logger.warning("Circuit breaker active, closing positions only")
            exit_actions = {"entered": [], "exited": [], "held": [], "errors": []}
            if hasattr(self.strategy, 'active_positions'):
                for symbol in list(self.strategy.active_positions.keys()):
                    try:
                        if await self.strategy.should_exit(symbol) if hasattr(self.strategy, 'should_exit') else True:
                            if await self._close_position(symbol):
                                exit_actions["exited"].append(symbol)
                                self.risk_manager.record_trade_result(0, symbol, "exit")
                    except Exception as e:
                        exit_actions["errors"].append(f"{symbol}: {e}")
            return {
                "strategy": exit_actions,
                "strategy_id": self.state.strategy_id,
                "strategy_name": STRATEGY_REGISTRY[self.state.strategy_id]["name"],
                "risk_status": {"level": risk_status.level.value, "warnings": risk_status.warnings, "circuit_breaker": True},
                "pnl": await self.calculate_pnl(),
                "timestamp": int(time.time() * 1000),
            }

        if self.state.portfolio_mode and self.portfolio_manager:
            portfolio_results = await self.portfolio_manager.run_cycle()
            combined_pnl = await self.portfolio_manager.get_combined_pnl()
            drift_report = await self.portfolio_manager.get_drift_report()

            self.state.per_strategy_performance = combined_pnl.get("strategy_breakdown", {})

            vault_value = combined_pnl.get("total_value", self.state.total_deposited)
            net_pnl = combined_pnl.get("combined_pnl", 0.0)
            pnl_pct = combined_pnl.get("combined_pnl_pct", 0.0)

            self.state.performance_history.append({
                "timestamp": int(time.time() * 1000),
                "vault_value": vault_value,
                "net_pnl": net_pnl,
                "pnl_pct": pnl_pct,
            })

            self._save_state()

            return {
                "portfolio_mode": True,
                "strategy_results": portfolio_results,
                "combined_pnl": combined_pnl,
                "drift_report": drift_report,
                "pnl": {
                    "vault_value": vault_value,
                    "net_pnl": net_pnl,
                    "pnl_pct": pnl_pct,
                    "total_deposited": self.state.total_deposited,
                },
                "timestamp": int(time.time() * 1000),
            }

        strategy_result = await self.strategy.run_cycle()

        for symbol in strategy_result.get("entered", []):
            entry_info = symbol if isinstance(symbol, str) else symbol.get("symbol", "")
            allowed = await self.risk_manager.should_allow_new_position(entry_info, 0)
            if not allowed:
                logger.warning(f"Risk manager blocked new position: {entry_info}")
                if entry_info in self.strategy.active_positions:
                    await self._close_position(entry_info)

        for symbol in strategy_result.get("exited", []):
            sym = symbol if isinstance(symbol, str) else symbol.get("symbol", str(symbol))
            self.risk_manager.record_trade_result(0, sym, "exit")

        if strategy_result.get("errors"):
            self.risk_manager.record_trade_result(0, "error", "error")

        # Only run rebalancer for delta_neutral strategy
        if self.state.strategy_id == "delta_neutral":
            rebalance_result = await self.rebalancer.run_check()
        else:
            rebalance_result = []

        pnl = await self.calculate_pnl()

        fee_result = await self.charge_fees()

        return {
            "strategy": strategy_result,
            "strategy_id": self.state.strategy_id,
            "strategy_name": STRATEGY_REGISTRY[self.state.strategy_id]["name"],
            "rebalances": rebalance_result,
            "pnl": pnl,
            "fees": fee_result,
            "timestamp": int(time.time() * 1000),
        }

    async def get_vault_info(self) -> dict:
        pnl = await self.calculate_pnl()
        strategy_info = STRATEGY_REGISTRY.get(self.state.strategy_id, {})

        result = {
            "vault_id": self.vault_id,
            "vault_name": self.state.vault_name,
            "description": self.state.description,
            "is_active": self.state.is_active,
            "created_at": self.state.created_at,
            "total_deposited": self.state.total_deposited,
            "vault_value": pnl["vault_value"],
            "share_price": pnl["share_price"],
            "total_shares": self.state.total_shares,
            "net_pnl": pnl["net_pnl"],
            "pnl_pct": pnl["pnl_pct"],
            "annualized_return": pnl["annualized_return"],
            "depositor_count": len(self.state.depositors),
            "active_positions": len(getattr(self.strategy, 'active_positions', {})),
            "strategy": {
                "id": self.state.strategy_id,
                "name": strategy_info.get("name", "Unknown"),
                "description": strategy_info.get("description", ""),
                "indicators": strategy_info.get("indicators", []),
                "risk_level": strategy_info.get("risk_level", "Unknown"),
                "expected_apy": strategy_info.get("expected_apy", "Unknown"),
            },
            "creator": self.state.creator_address,
            "cloned_from": self.state.cloned_from,
            "clone_count": self.state.clone_count,
            "social_stats": self.state.social_stats,
            "risk": {
                "circuit_breaker_active": self.risk_manager.circuit_breaker_active,
                "circuit_breaker_reason": self.risk_manager.circuit_breaker_reason,
                "emergency_stop_active": self.risk_manager.emergency_stop_active,
                "emergency_stop_type": self.risk_manager.emergency_stop_type.value if self.risk_manager.emergency_stop_type else None,
                "consecutive_losses": self.risk_manager.consecutive_losses,
                "peak_value": self.risk_manager.peak_value,
            },
            "portfolio_mode": self.state.portfolio_mode,
            "portfolio_allocations": self.state.portfolio_allocations,
            "per_strategy_performance": self.state.per_strategy_performance,
            "fees": self.get_fee_info()["fee_structure"],
        }

        if self.state.portfolio_mode and self.portfolio_manager:
            combined_pnl = await self.portfolio_manager.get_combined_pnl()
            drift_report = await self.portfolio_manager.get_drift_report()
            result["portfolio"] = {
                "combined_pnl": combined_pnl,
                "drift_report": drift_report,
                "strategy_status": self.portfolio_manager.get_status(),
            }

        return result

    async def configure_portfolio(self, allocations: dict[str, float], rebalance_threshold: float = 0.05) -> dict:
        for sid in allocations:
            if sid not in STRATEGY_REGISTRY:
                raise ValueError(f"Unknown strategy: {sid}")

        total = sum(allocations.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Allocations must sum to ~1.0, got {total:.4f}")

        for pct in allocations.values():
            if pct < 0 or pct > 1:
                raise ValueError(f"Allocation must be between 0 and 1")

        if self.state.portfolio_mode and self.portfolio_manager:
            errors = self.portfolio_manager.update_allocations(allocations)
            if errors:
                raise ValueError("; ".join(errors))
            self.portfolio_manager.config.rebalance_threshold = rebalance_threshold
        else:
            portfolio_config = PortfolioConfig(
                allocations=allocations,
                rebalance_threshold=rebalance_threshold,
            )
            self.portfolio_manager = PortfolioManager(
                self.client, portfolio_config, total_capital=self.state.total_deposited
            )

        self.state.portfolio_mode = True
        self.state.portfolio_allocations = allocations
        self._save_state()

        logger.info(f"Portfolio configured for vault {self.vault_id}: {allocations}")
        return {
            "status": "configured",
            "vault_id": self.vault_id,
            "portfolio_mode": True,
            "allocations": allocations,
            "rebalance_threshold": rebalance_threshold,
        }

    async def get_portfolio_status(self) -> dict:
        if not self.state.portfolio_mode or not self.portfolio_manager:
            return {
                "portfolio_mode": False,
                "message": "Portfolio mode not enabled. Configure allocations first.",
            }

        combined_pnl = await self.portfolio_manager.get_combined_pnl()
        drift_report = await self.portfolio_manager.get_drift_report()
        portfolio_status = self.portfolio_manager.get_status()

        return {
            "portfolio_mode": True,
            "allocations": self.state.portfolio_allocations,
            "combined_pnl": combined_pnl,
            "drift_report": drift_report,
            "portfolio_status": portfolio_status,
            "per_strategy_performance": self.state.per_strategy_performance,
        }

    async def rebalance_portfolio(self) -> dict:
        if not self.state.portfolio_mode or not self.portfolio_manager:
            raise RuntimeError("Portfolio mode not enabled")

        result = await self.portfolio_manager.rebalance()
        self.state.per_strategy_performance = (
            await self.portfolio_manager.get_combined_pnl()
        ).get("strategy_breakdown", {})
        self._save_state()

        logger.info(f"Portfolio rebalanced for vault {self.vault_id}: {result.get('status')}")
        return result

    async def emergency_stop(self, stop_type: str = "kill_switch") -> dict:
        result = await self.risk_manager.emergency_stop(stop_type)
        if stop_type == "kill_switch" and hasattr(self.strategy, 'active_positions'):
            for symbol in list(self.strategy.active_positions.keys()):
                try:
                    await self._close_position(symbol)
                    logger.info(f"Emergency closed {symbol}")
                except Exception as e:
                    logger.error(f"Emergency close failed for {symbol}: {e}")
        return result

    async def resume_trading(self) -> dict:
        return await self.risk_manager.resume_trading()

    async def get_risk_status(self) -> dict:
        self._sync_risk_positions()
        risk_status = await self.risk_manager.check_risk_limits(self.state)
        report = await self.risk_manager.get_risk_report()
        return {
            "level": risk_status.level.value,
            "daily_pnl_pct": risk_status.daily_pnl_pct,
            "drawdown_pct": risk_status.drawdown_pct,
            "consecutive_losses": risk_status.consecutive_losses,
            "circuit_breaker_active": risk_status.circuit_breaker_active,
            "emergency_stop_active": risk_status.emergency_stop_active,
            "emergency_stop_type": risk_status.emergency_stop_type,
            "warnings": risk_status.warnings,
            "violations": risk_status.violations,
            "position_usage_pct": risk_status.position_usage_pct,
            "sector_exposure": risk_status.sector_exposure,
            "correlated_exposure": risk_status.correlated_exposure,
            "report": report,
        }

    def configure_risk(self, updates: dict) -> dict:
        config = self.risk_manager.update_config(updates)
        return {"status": "updated", "config": {k: v for k, v in config.__dict__.items() if not k.startswith('_')}}

    async def charge_fees(self) -> dict:
        vault_value = await self.get_total_vault_value()
        now_ms = int(time.time() * 1000)
        last_charge = self.state.fee_config.get("last_fee_charge_time", 0)

        mgmt_fee_annual = self.state.fee_config.get("management_fee_annual", 0.005)
        perf_fee_rate = self.state.fee_config.get("performance_fee", 0.10)
        protocol_fee_rate = self.state.fee_config.get("protocol_fee", 0.005)
        high_water_mark = self.state.fee_config.get("high_water_mark", 0.0)

        days_elapsed = 0.0
        if last_charge > 0:
            days_elapsed = (now_ms - last_charge) / (86400 * 1000)
        elif self.state.created_at > 0:
            days_elapsed = (now_ms - self.state.created_at) / (86400 * 1000)
            last_charge = self.state.created_at

        if days_elapsed < 1.0:
            return {"status": "skipped", "reason": "less_than_one_day_since_last_charge"}

        mgmt_fee = vault_value * (mgmt_fee_annual / 365) * days_elapsed

        perf_fee = 0.0
        if high_water_mark <= 0 and vault_value > self.state.total_deposited:
            high_water_mark = self.state.total_deposited

        if vault_value > high_water_mark and high_water_mark > 0:
            profit = vault_value - high_water_mark
            perf_fee = profit * perf_fee_rate
            self.state.fee_config["high_water_mark"] = vault_value
        elif high_water_mark <= 0 and vault_value > 0:
            self.state.fee_config["high_water_mark"] = vault_value

        protocol_fee_amount = (mgmt_fee + perf_fee) * protocol_fee_rate
        total_fee = mgmt_fee + perf_fee + protocol_fee_amount

        self.state.fee_config["last_fee_charge_time"] = now_ms
        self.state.fee_config["high_water_mark"] = self.state.fee_config.get("high_water_mark", vault_value)

        self.state.fee_accrual["creator_management_fees_earned"] = self.state.fee_accrual.get("creator_management_fees_earned", 0.0) + mgmt_fee
        self.state.fee_accrual["creator_performance_fees_earned"] = self.state.fee_accrual.get("creator_performance_fees_earned", 0.0) + perf_fee
        self.state.fee_accrual["protocol_fees_earned"] = self.state.fee_accrual.get("protocol_fees_earned", 0.0) + protocol_fee_amount

        charge_record = {
            "timestamp": now_ms,
            "vault_value": vault_value,
            "days_charged": round(days_elapsed, 2),
            "management_fee": round(mgmt_fee, 8),
            "performance_fee": round(perf_fee, 8),
            "protocol_fee": round(protocol_fee_amount, 8),
            "total_fee": round(total_fee, 8),
            "high_water_mark": self.state.fee_config["high_water_mark"],
        }
        history = self.state.fee_accrual.get("fee_charge_history", [])
        history.append(charge_record)
        self.state.fee_accrual["fee_charge_history"] = history[-100:]

        self.state.total_fees_paid += total_fee
        self._save_state()

        logger.info(
            f"Fees charged for vault {self.vault_id}: "
            f"mgmt=${mgmt_fee:.6f}, perf=${perf_fee:.6f}, protocol=${protocol_fee_amount:.6f}"
        )

        return {
            "status": "charged",
            "management_fee": mgmt_fee,
            "performance_fee": perf_fee,
            "protocol_fee": protocol_fee_amount,
            "total_fee": total_fee,
            "days_charged": days_elapsed,
            "high_water_mark": self.state.fee_config["high_water_mark"],
        }

    def get_fee_info(self) -> dict:
        mgmt = self.state.fee_config.get("management_fee_annual", 0.005)
        perf = self.state.fee_config.get("performance_fee", 0.10)
        proto = self.state.fee_config.get("protocol_fee", 0.005)
        hwm = self.state.fee_config.get("high_water_mark", 0.0)
        last = self.state.fee_config.get("last_fee_charge_time", 0)

        creator_mgmt = self.state.fee_accrual.get("creator_management_fees_earned", 0.0)
        creator_perf = self.state.fee_accrual.get("creator_performance_fees_earned", 0.0)
        protocol_accrued = self.state.fee_accrual.get("protocol_fees_earned", 0.0)
        creator_withdrawn = self.state.fee_accrual.get("creator_fees_withdrawn", 0.0)

        return {
            "vault_id": self.vault_id,
            "fee_structure": {
                "management_fee_annual": mgmt,
                "management_fee_annual_pct": f"{mgmt * 100:.1f}%",
                "performance_fee": perf,
                "performance_fee_pct": f"{perf * 100:.0f}%",
                "protocol_fee": proto,
                "protocol_fee_pct": f"{proto * 100:.1f}%",
            },
            "high_water_mark": hwm,
            "last_fee_charge_time": last,
            "accrued": {
                "creator_management_fees": creator_mgmt,
                "creator_performance_fees": creator_perf,
                "creator_total_earned": creator_mgmt + creator_perf,
                "creator_fees_withdrawn": creator_withdrawn,
                "creator_fees_claimable": creator_mgmt + creator_perf - creator_withdrawn,
                "protocol_fees_earned": protocol_accrued,
            },
        }

    async def get_creator_dashboard(self, creator_address: str) -> dict:
        if self.state.creator_address and self.state.creator_address != creator_address:
            raise ValueError("Not the creator of this vault")

        vault_value = await self.get_total_vault_value()
        fee_info = self.get_fee_info()
        accrued = fee_info["accrued"]

        history = self.state.fee_accrual.get("fee_charge_history", [])
        recent_charges = history[-30:]

        total_creator_earned = accrued["creator_total_earned"]
        total_protocol_earned = accrued["protocol_fees_earned"]

        daily_avg_creator = 0.0
        if self.state.created_at > 0:
            age_days = (time.time() * 1000 - self.state.created_at) / (86400 * 1000)
            if age_days > 0:
                daily_avg_creator = total_creator_earned / age_days

        return {
            "creator_address": creator_address,
            "vault_id": self.vault_id,
            "vault_name": self.state.vault_name or self.vault_id,
            "strategy_id": self.state.strategy_id,
            "strategy_name": STRATEGY_REGISTRY.get(self.state.strategy_id, {}).get("name", "Unknown"),
            "aum": vault_value,
            "depositor_count": len(self.state.depositors),
            "total_deposited": self.state.total_deposited,
            "fee_earnings": {
                "management_fees_earned": accrued["creator_management_fees"],
                "performance_fees_earned": accrued["creator_performance_fees"],
                "total_earned": total_creator_earned,
                "claimable": accrued["creator_fees_claimable"],
                "withdrawn": accrued["creator_fees_withdrawn"],
                "daily_average": daily_avg_creator,
            },
            "protocol_fees": {
                "total_earned": total_protocol_earned,
                "withdrawn": self.state.fee_accrual.get("protocol_fees_withdrawn", 0.0),
            },
            "fee_structure": fee_info["fee_structure"],
            "high_water_mark": fee_info["high_water_mark"],
            "recent_fee_charges": recent_charges,
            "vault_active": self.state.is_active,
        }

    async def withdraw_creator_fees(self, creator_address: str, amount: Optional[float] = None) -> dict:
        if self.state.creator_address and self.state.creator_address != creator_address:
            raise ValueError("Not the creator of this vault")

        fee_info = self.get_fee_info()
        claimable = fee_info["accrued"]["creator_fees_claimable"]

        if claimable <= 0:
            return {"status": "no_fees", "message": "No claimable fees available"}

        withdraw_amount = min(amount or claimable, claimable)

        self.state.fee_accrual["creator_fees_withdrawn"] = self.state.fee_accrual.get("creator_fees_withdrawn", 0.0) + withdraw_amount
        self._save_state()

        logger.info(f"Creator {creator_address} withdrew ${withdraw_amount:.6f} in fees from vault {self.vault_id}")

        return {
            "status": "withdrawn",
            "creator_address": creator_address,
            "amount": withdraw_amount,
            "remaining_claimable": claimable - withdraw_amount,
            "total_earned": fee_info["accrued"]["creator_total_earned"],
            "total_withdrawn": self.state.fee_accrual["creator_fees_withdrawn"],
        }
