import time
import logging
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    OK = "ok"
    WARNING = "warning"
    VIOLATION = "violation"


class EmergencyStopType(Enum):
    KILL_SWITCH = "kill_switch"
    GRADUAL_UNWIND = "gradual_unwind"


@dataclass
class RiskConfig:
    daily_loss_limit_pct: float = 5.0
    max_drawdown_pct: float = 10.0
    consecutive_losses_limit: int = 3
    max_position_size_pct: float = 25.0
    max_correlated_exposure: float = 50.0
    max_sector_exposure: float = 30.0
    enable_circuit_breaker: bool = True
    funding_rate_flip_protection: bool = True
    fixed_risk_per_trade_pct: float = 1.0
    position_sizing_method: str = "fixed_risk"
    kelly_fraction: float = 0.25
    volatility_adjust: bool = True
    volatility_lookback_hours: int = 24
    volatility_high_threshold: float = 5.0
    gradual_unwind_pct_per_hour: float = 10.0

    SECTOR_MAP: dict = field(default_factory=lambda: {
        "BTC": "majors",
        "ETH": "majors",
        "SOL": "L1s",
        "AVAX": "L1s",
        "MATIC": "L1s",
        "ARB": "L1s",
        "DOGE": "memecoins",
        "SHIB": "memecoins",
        "PEPE": "memecoins",
        "WIF": "memecoins",
        "BONK": "memecoins",
        "MEME": "memecoins",
        "LINK": "oracle",
        "PYTH": "oracle",
        "AAVE": "defi",
        "UNI": "defi",
        "CRV": "defi",
    })

    CORRELATION_GROUPS: dict = field(default_factory=lambda: {
        "btc_correlated": ["BTC", "BCH", "BSV"],
        "eth_correlated": ["ETH", "MATIC", "ARB", "OP"],
        "sol_correlated": ["SOL", "BONK", "WIF", "JUP"],
        "meme_correlated": ["DOGE", "SHIB", "PEPE", "WIF", "BONK", "MEME", "FLOKI"],
        "defi_correlated": ["AAVE", "UNI", "CRV", "COMP", "MKR"],
    })


@dataclass
class TradeRecord:
    timestamp: int
    pnl: float
    symbol: str
    side: str


@dataclass
class RiskStatus:
    level: RiskLevel
    daily_pnl_pct: float
    drawdown_pct: float
    consecutive_losses: int
    circuit_breaker_active: bool
    emergency_stop_active: bool
    emergency_stop_type: Optional[str]
    warnings: list
    violations: list
    position_usage_pct: float
    sector_exposure: dict
    correlated_exposure: dict


class RiskManager:
    def __init__(self, config: Optional[RiskConfig] = None, state_dir: str = "data"):
        self.config = config or RiskConfig()
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "risk_state.json"

        self.trade_history: list[TradeRecord] = []
        self.consecutive_losses: int = 0
        self.peak_value: float = 0.0
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_reason: Optional[str] = None
        self.emergency_stop_active: bool = False
        self.emergency_stop_type: Optional[EmergencyStopType] = None
        self.emergency_stop_time: Optional[int] = None
        self.current_positions: dict = {}

        self._load_state()

    def _load_state(self):
        if self.state_file.exists():
            try:
                raw = json.loads(self.state_file.read_text())
                self.peak_value = raw.get("peak_value", 0.0)
                self.circuit_breaker_active = raw.get("circuit_breaker_active", False)
                self.circuit_breaker_reason = raw.get("circuit_breaker_reason")
                self.emergency_stop_active = raw.get("emergency_stop_active", False)
                stop_type = raw.get("emergency_stop_type")
                self.emergency_stop_type = EmergencyStopType(stop_type) if stop_type else None
                self.emergency_stop_time = raw.get("emergency_stop_time")
                self.consecutive_losses = raw.get("consecutive_losses", 0)
                trades = raw.get("trade_history", [])
                self.trade_history = [
                    TradeRecord(
                        timestamp=t["timestamp"],
                        pnl=t["pnl"],
                        symbol=t["symbol"],
                        side=t["side"],
                    )
                    for t in trades
                ]
            except Exception as e:
                logger.warning(f"Failed to load risk state: {e}")

    def _save_state(self):
        data = {
            "peak_value": self.peak_value,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "emergency_stop_active": self.emergency_stop_active,
            "emergency_stop_type": self.emergency_stop_type.value if self.emergency_stop_type else None,
            "emergency_stop_time": self.emergency_stop_time,
            "consecutive_losses": self.consecutive_losses,
            "trade_history": [
                {"timestamp": t.timestamp, "pnl": t.pnl, "symbol": t.symbol, "side": t.side}
                for t in self.trade_history[-500:]
            ],
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def update_positions(self, positions: dict):
        self.current_positions = positions

    def record_trade_result(self, pnl: float, symbol: str = "", side: str = ""):
        trade = TradeRecord(
            timestamp=int(time.time() * 1000),
            pnl=pnl,
            symbol=symbol,
            side=side,
        )
        self.trade_history.append(trade)

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        self._check_circuit_breakers(pnl)
        self._save_state()

    def update_peak_value(self, current_value: float):
        if current_value > self.peak_value:
            self.peak_value = current_value

    def _get_daily_pnl(self, total_deposited: float) -> float:
        now = int(time.time() * 1000)
        day_ago = now - 24 * 3600 * 1000
        daily_trades = [t for t in self.trade_history if t.timestamp >= day_ago]
        daily_pnl = sum(t.pnl for t in daily_trades)
        if total_deposited <= 0:
            return 0.0
        return (daily_pnl / total_deposited) * 100

    def _get_drawdown(self, current_value: float) -> float:
        if self.peak_value <= 0:
            return 0.0
        if current_value >= self.peak_value:
            return 0.0
        return ((self.peak_value - current_value) / self.peak_value) * 100

    def _check_circuit_breakers(self, latest_pnl: float = 0.0):
        if not self.config.enable_circuit_breaker:
            return

        if self.circuit_breaker_active:
            return

        if self.consecutive_losses >= self.config.consecutive_losses_limit:
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = (
                f"Consecutive losses limit reached: {self.consecutive_losses} >= {self.config.consecutive_losses_limit}"
            )
            logger.warning(f"CIRCUIT BREAKER: {self.circuit_breaker_reason}")
            return

        if self.config.funding_rate_flip_protection and latest_pnl < 0:
            for symbol, pos in self.current_positions.items():
                if hasattr(pos, 'side') and pos.side == 'short' and latest_pnl < 0:
                    pass

    async def check_risk_limits(self, vault_state) -> RiskStatus:
        warnings = []
        violations = []

        total_deposited = getattr(vault_state, 'total_deposited', 0)
        current_value = total_deposited

        try:
            if hasattr(vault_state, 'total_funding_earned') and hasattr(vault_state, 'total_fees_paid'):
                current_value = total_deposited + getattr(vault_state, 'total_funding_earned', 0) - getattr(vault_state, 'total_fees_paid', 0)
        except Exception:
            pass

        self.update_peak_value(current_value)

        daily_pnl_pct = self._get_daily_pnl(total_deposited)
        drawdown_pct = self._get_drawdown(current_value)

        if daily_pnl_pct < -(self.config.daily_loss_limit_pct * 0.8):
            warnings.append(f"Approaching daily loss limit: {daily_pnl_pct:.2f}% (limit: -{self.config.daily_loss_limit_pct}%)")
        if daily_pnl_pct <= -self.config.daily_loss_limit_pct:
            violations.append(f"Daily loss limit breached: {daily_pnl_pct:.2f}% (limit: -{self.config.daily_loss_limit_pct}%)")
            if self.config.enable_circuit_breaker and not self.circuit_breaker_active:
                self.circuit_breaker_active = True
                self.circuit_breaker_reason = f"Daily loss limit: {daily_pnl_pct:.2f}%"

        if drawdown_pct > self.config.max_drawdown_pct * 0.8:
            warnings.append(f"Approaching max drawdown: {drawdown_pct:.2f}% (limit: {self.config.max_drawdown_pct}%)")
        if drawdown_pct >= self.config.max_drawdown_pct:
            violations.append(f"Max drawdown breached: {drawdown_pct:.2f}% (limit: {self.config.max_drawdown_pct}%)")
            if self.config.enable_circuit_breaker and not self.circuit_breaker_active:
                self.circuit_breaker_active = True
                self.circuit_breaker_reason = f"Max drawdown: {drawdown_pct:.2f}%"

        if self.consecutive_losses >= self.config.consecutive_losses_limit - 1:
            warnings.append(f"Consecutive losses: {self.consecutive_losses} (limit: {self.config.consecutive_losses_limit})")
        if self.consecutive_losses >= self.config.consecutive_losses_limit:
            violations.append(f"Consecutive loss limit reached: {self.consecutive_losses}")

        sector_exposure = self._calculate_sector_exposure()
        for sector, pct in sector_exposure.items():
            if pct > self.config.max_sector_exposure * 0.8:
                warnings.append(f"Sector '{sector}' approaching limit: {pct:.1f}% (max: {self.config.max_sector_exposure}%)")
            if pct > self.config.max_sector_exposure:
                violations.append(f"Sector '{sector}' over limit: {pct:.1f}% (max: {self.config.max_sector_exposure}%)")

        correlated_exposure = self._calculate_correlated_exposure()
        for group, pct in correlated_exposure.items():
            if pct > self.config.max_correlated_exposure * 0.8:
                warnings.append(f"Correlation group '{group}' approaching limit: {pct:.1f}%")
            if pct > self.config.max_correlated_exposure:
                violations.append(f"Correlation group '{group}' over limit: {pct:.1f}%")

        position_usage = 0.0
        if self.current_positions and total_deposited > 0:
            total_notional = sum(
                getattr(pos, 'size', 0) * getattr(pos, 'entry_price', 0)
                for pos in self.current_positions.values()
            )
            position_usage = (total_notional / total_deposited) * 100

        if violations:
            level = RiskLevel.VIOLATION
        elif warnings:
            level = RiskLevel.WARNING
        else:
            level = RiskLevel.OK

        self._save_state()

        return RiskStatus(
            level=level,
            daily_pnl_pct=daily_pnl_pct,
            drawdown_pct=drawdown_pct,
            consecutive_losses=self.consecutive_losses,
            circuit_breaker_active=self.circuit_breaker_active,
            emergency_stop_active=self.emergency_stop_active,
            emergency_stop_type=self.emergency_stop_type.value if self.emergency_stop_type else None,
            warnings=warnings,
            violations=violations,
            position_usage_pct=position_usage,
            sector_exposure=sector_exposure,
            correlated_exposure=correlated_exposure,
        )

    async def should_allow_new_position(self, symbol: str, size: float) -> bool:
        if self.emergency_stop_active:
            logger.warning(f"Position rejected: emergency stop active ({self.emergency_stop_type})")
            return False

        if self.circuit_breaker_active:
            logger.warning(f"Position rejected: circuit breaker active ({self.circuit_breaker_reason})")
            return False

        if size <= 0:
            return False

        total_deposited = 0
        for pos in self.current_positions.values():
            total_deposited += getattr(pos, 'size', 0) * getattr(pos, 'entry_price', 0)

        position_notional = size
        if total_deposited > 0:
            position_pct = (position_notional / total_deposited) * 100 if total_deposited > 0 else 0
            if position_pct > self.config.max_position_size_pct:
                logger.warning(f"Position rejected: size {position_pct:.1f}% exceeds max {self.config.max_position_size_pct}%")
                return False

        sector = self.config.SECTOR_MAP.get(symbol.upper(), "other")
        sector_exposure = self._calculate_sector_exposure()
        current_sector_pct = sector_exposure.get(sector, 0)
        new_position_pct = (position_notional / total_deposited * 100) if total_deposited > 0 else 0
        if current_sector_pct + new_position_pct > self.config.max_sector_exposure:
            logger.warning(f"Position rejected: sector '{sector}' would exceed {self.config.max_sector_exposure}%")
            return False

        correlated = self._calculate_correlated_exposure()
        for group_name, symbols in self.config.CORRELATION_GROUPS.items():
            if symbol.upper() in symbols:
                current_group_pct = correlated.get(group_name, 0)
                new_pct = (position_notional / total_deposited * 100) if total_deposited > 0 else 0
                if current_group_pct + new_pct > self.config.max_correlated_exposure:
                    logger.warning(f"Position rejected: correlation group '{group_name}' would exceed {self.config.max_correlated_exposure}%")
                    return False

        return True

    def calculate_position_size(
        self,
        capital: float,
        win_rate: float = 0.55,
        avg_win_loss_ratio: float = 1.5,
        volatility: Optional[float] = None,
    ) -> float:
        if capital <= 0:
            return 0.0

        if self.config.position_sizing_method == "kelly":
            if win_rate <= 0 or win_rate >= 1:
                kelly_pct = self.config.fixed_risk_per_trade_pct / 100
            else:
                kelly_pct = win_rate - ((1 - win_rate) / avg_win_loss_ratio)
                kelly_pct = max(0, kelly_pct)
            fraction = kelly_pct * self.config.kelly_fraction
            size = capital * fraction

        elif self.config.position_sizing_method == "volatility_adjusted" and volatility is not None and volatility > 0:
            base_risk = self.config.fixed_risk_per_trade_pct / 100
            vol_factor = max(0.2, min(1.0, self.config.volatility_high_threshold / volatility))
            size = capital * base_risk * vol_factor

        else:
            size = capital * (self.config.fixed_risk_per_trade_pct / 100)

        max_size = capital * (self.config.max_position_size_pct / 100)
        size = min(size, max_size)

        return max(0, size)

    def _calculate_sector_exposure(self) -> dict[str, float]:
        if not self.current_positions:
            return {}

        total_notional = sum(
            getattr(pos, 'size', 0) * getattr(pos, 'entry_price', 0)
            for pos in self.current_positions.values()
        )
        if total_notional <= 0:
            return {}

        sector_totals: dict[str, float] = {}
        for symbol, pos in self.current_positions.items():
            sector = self.config.SECTOR_MAP.get(symbol.upper(), "other")
            notional = getattr(pos, 'size', 0) * getattr(pos, 'entry_price', 0)
            sector_totals[sector] = sector_totals.get(sector, 0) + notional

        return {
            sector: (notional / total_notional) * 100
            for sector, notional in sector_totals.items()
        }

    def _calculate_correlated_exposure(self) -> dict[str, float]:
        if not self.current_positions:
            return {}

        total_notional = sum(
            getattr(pos, 'size', 0) * getattr(pos, 'entry_price', 0)
            for pos in self.current_positions.values()
        )
        if total_notional <= 0:
            return {}

        group_totals: dict[str, float] = {}
        for group_name, symbols in self.config.CORRELATION_GROUPS.items():
            group_notional = 0.0
            for symbol in symbols:
                pos = self.current_positions.get(symbol)
                if pos:
                    group_notional += getattr(pos, 'size', 0) * getattr(pos, 'entry_price', 0)
            if group_notional > 0:
                group_totals[group_name] = (group_notional / total_notional) * 100

        return group_totals

    async def emergency_stop(self, stop_type: str = "kill_switch") -> dict:
        self.emergency_stop_active = True
        self.emergency_stop_type = EmergencyStopType(stop_type)
        self.emergency_stop_time = int(time.time() * 1000)
        self._save_state()

        logger.critical(f"EMERGENCY STOP ACTIVATED: {stop_type}")
        return {
            "status": "emergency_stop_activated",
            "stop_type": stop_type,
            "timestamp": self.emergency_stop_time,
            "active_positions": len(self.current_positions),
        }

    async def resume_trading(self) -> dict:
        self.emergency_stop_active = False
        self.emergency_stop_type = None
        self.emergency_stop_time = None
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = None
        self.consecutive_losses = 0
        self._save_state()

        logger.info("Trading resumed: all stops cleared")
        return {
            "status": "trading_resumed",
            "timestamp": int(time.time() * 1000),
        }

    async def get_risk_report(self) -> dict:
        now = int(time.time() * 1000)
        day_ago = now - 24 * 3600 * 1000
        recent_trades = [t for t in self.trade_history if t.timestamp >= day_ago]
        daily_pnl = sum(t.pnl for t in recent_trades)
        winning_trades = [t for t in recent_trades if t.pnl > 0]
        losing_trades = [t for t in recent_trades if t.pnl < 0]
        win_rate = (len(winning_trades) / len(recent_trades) * 100) if recent_trades else 0

        return {
            "emergency_stop_active": self.emergency_stop_active,
            "emergency_stop_type": self.emergency_stop_type.value if self.emergency_stop_type else None,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "consecutive_losses": self.consecutive_losses,
            "peak_value": self.peak_value,
            "daily_pnl": daily_pnl,
            "daily_trade_count": len(recent_trades),
            "daily_win_rate": round(win_rate, 1),
            "daily_winning_trades": len(winning_trades),
            "daily_losing_trades": len(losing_trades),
            "sector_exposure": self._calculate_sector_exposure(),
            "correlated_exposure": self._calculate_correlated_exposure(),
            "config": {
                "daily_loss_limit_pct": self.config.daily_loss_limit_pct,
                "max_drawdown_pct": self.config.max_drawdown_pct,
                "consecutive_losses_limit": self.config.consecutive_losses_limit,
                "max_position_size_pct": self.config.max_position_size_pct,
                "max_correlated_exposure": self.config.max_correlated_exposure,
                "max_sector_exposure": self.config.max_sector_exposure,
                "position_sizing_method": self.config.position_sizing_method,
                "fixed_risk_per_trade_pct": self.config.fixed_risk_per_trade_pct,
                "kelly_fraction": self.config.kelly_fraction,
                "enable_circuit_breaker": self.config.enable_circuit_breaker,
                "funding_rate_flip_protection": self.config.funding_rate_flip_protection,
            },
        }

    def update_config(self, updates: dict) -> RiskConfig:
        for key, value in updates.items():
            if hasattr(self.config, key) and value is not None:
                setattr(self.config, key, value)
        self._save_state()
        return self.config
