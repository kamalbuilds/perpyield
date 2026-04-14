import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pacifica.client import PacificaClient, sf
from indicators.ichimoku import IchimokuCalculator, IchimokuSignal, IchimokuTrend

logger = logging.getLogger(__name__)


class BreakoutDirection(Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class BreakoutSignal:
    symbol: str
    direction: BreakoutDirection
    volatility_score: float  # 0-100
    entry_price: float
    atr: float  # Average True Range
    stop_loss: float
    take_profit: float
    indicators: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class BreakoutPosition:
    symbol: str
    direction: BreakoutDirection
    size: float
    entry_price: float
    atr: float
    stop_loss: float
    take_profit: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    trailing_stop: float = 0.0


@dataclass
class VolatilityBreakoutConfig:
    # ATR settings
    atr_period: int = 14
    atr_multiplier_entry: float = 0.5  # Entry when price moves 0.5 ATR
    atr_multiplier_stop: float = 1.5   # Stop at 1.5 ATR
    atr_multiplier_profit: float = 3.0  # Take profit at 3 ATR

    # Volatility filters
    min_atr_pct: float = 1.0  # Minimum ATR as % of price
    max_atr_pct: float = 8.0  # Maximum ATR (avoid super volatile)

    # Volume confirmation
    volume_confirm_periods: int = 3
    volume_threshold: float = 1.3  # 30% above average volume

    # Breakout levels
    lookback_periods: int = 20  # For calculating highs/lows

    # Position sizing
    min_volume_24h: float = 100000.0
    max_positions: int = 4
    position_size_pct: float = 0.10
    max_leverage: float = 2.0

    # Time filters
    max_hold_hours: int = 48


class VolatilityBreakoutStrategy:
    """
    Volatility Breakout Strategy - Pacifica Expert Mode compatible

    Waits for consolidation (low volatility period) then enters on breakout
    with volume confirmation. Uses ATR-based position sizing and stops.
    Captures explosive moves after compression.
    """

    STRATEGY_ID = "volatility_breakout"
    STRATEGY_NAME = "Volatility Breakout"
    STRATEGY_DESC = "Breakout strategy using ATR + volume confirmation"
    INDICATORS = ["ATR", "Volume", "Support/Resistance", "Ichimoku Cloud"]

    def __init__(self, client: PacificaClient, config: Optional[VolatilityBreakoutConfig] = None):
        self.client = client
        self.config = config or VolatilityBreakoutConfig()
        self.active_positions: dict[str, BreakoutPosition] = {}
        self.signal_history: List[BreakoutSignal] = []
        self.ichimoku = IchimokuCalculator()

    async def calculate_atr(self, candles: list, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(candles) < period + 1:
            return 0.0

        true_ranges = []
        for i in range(1, min(period + 1, len(candles))):
            high = sf(candles[-i].high)
            low = sf(candles[-i].low)
            prev_close = sf(candles[-(i+1)].close)

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)

            true_ranges.append(max(tr1, tr2, tr3))

        if not true_ranges:
            return 0.0

        return sum(true_ranges) / len(true_ranges)

    async def calculate_volume_ma(self, candles: list, period: int = 20) -> float:
        """Calculate volume moving average."""
        if len(candles) < period:
            return 0.0

        volumes = [sf(c.volume) for c in candles[-period:]]
        if not volumes or any(v == 0 for v in volumes):
            return 0.0

        return sum(volumes) / len(volumes)

    async def find_support_resistance(self, candles: list, period: int = 20) -> tuple[float, float]:
        """Find recent support and resistance levels."""
        if len(candles) < period:
            return 0.0, 0.0

        recent_candles = candles[-period:]
        highs = [sf(c.high) for c in recent_candles]
        lows = [sf(c.low) for c in recent_candles]

        resistance = max(highs)
        support = min(lows)

        return support, resistance

    def calculate_volatility_score(
        self,
        current_price: float,
        atr: float,
        volume_ratio: float,
        is_breaking_out: bool
    ) -> float:
        """Calculate volatility breakout score (0-100)."""
        score = 0.0

        # ATR contribution (30 points)
        atr_pct = (atr / current_price) * 100 if current_price > 0 else 0
        if self.config.min_atr_pct <= atr_pct <= self.config.max_atr_pct:
            score += min(30, atr_pct * 5)

        # Volume confirmation (40 points)
        if volume_ratio >= self.config.volume_threshold:
            score += min(40, (volume_ratio - 1) * 100)

        # Breakout confirmation (30 points)
        if is_breaking_out:
            score += 30

        return min(100, score)

    async def scan_opportunities(self) -> list[BreakoutSignal]:
        """Scan for volatility breakout opportunities."""
        opportunities = []

        try:
            prices = await self.client.get_prices()
            markets = await self.client.get_markets()
            leverage_map = {m.symbol: m.max_leverage for m in markets}
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return opportunities

        for price_data in prices:
            symbol = price_data.symbol

            # Skip if already in position
            if symbol in self.active_positions:
                continue

            try:
                # Get candles for analysis
                end_ms = int(time.time() * 1000)
                start_ms = end_ms - (48 * 3600 * 1000)  # 48 hours
                candles = await self.client.get_candles(symbol, "1h", start_ms, end_ms)

                if len(candles) < self.config.lookback_periods + 5:
                    continue

                current_price = sf(price_data.mark)

                # Calculate indicators
                atr = await self.calculate_atr(candles, self.config.atr_period)
                volume_ma = await self.calculate_volume_ma(candles, 20)
                support, resistance = await self.find_support_resistance(
                    candles, self.config.lookback_periods
                )

                # Volume check
                current_volume = sf(price_data.volume_24h)
                volume_ratio = (current_volume / volume_ma) if volume_ma > 0 else 0

                # ATR percentage check
                atr_pct = (atr / current_price) * 100 if current_price > 0 else 0

                if atr_pct < self.config.min_atr_pct:
                    continue  # Too low volatility

                if atr_pct > self.config.max_atr_pct:
                    continue  # Too high volatility (chaos)

                if current_volume < self.config.min_volume_24h:
                    continue

                # Check for breakout
                direction = BreakoutDirection.NONE
                is_breaking_out = False

                # Long breakout: price breaks above resistance with volume
                if current_price > resistance * 1.005 and volume_ratio >= self.config.volume_threshold:
                    # Confirm with recent consolidation
                    recent_range = resistance - support
                    if recent_range / current_price < 0.05:  # 5% range = consolidation
                        direction = BreakoutDirection.LONG
                        is_breaking_out = True

                # Short breakout: price breaks below support with volume
                elif current_price < support * 0.995 and volume_ratio >= self.config.volume_threshold:
                    recent_range = resistance - support
                    if recent_range / current_price < 0.05:
                        direction = BreakoutDirection.SHORT
                        is_breaking_out = True

                if direction == BreakoutDirection.NONE:
                    continue

                ichimoku_data = {}
                cloud_compression_bonus = 0.0
                if len(candles) >= 52:
                    cloud = self.ichimoku.calculate(candles, current_price)
                    if cloud:
                        compression = self.ichimoku.cloud_compression(cloud, current_price)
                        breakout_type = self.ichimoku.cloud_breakout_signal(cloud, current_price)
                        ichimoku_data = {
                            "tenkan_sen": cloud.tenkan_sen,
                            "kijun_sen": cloud.kijun_sen,
                            "cloud_top": cloud.cloud_top,
                            "cloud_bottom": cloud.cloud_bottom,
                            "cloud_color": cloud.cloud_color,
                            "cloud_thickness_pct": (cloud.cloud_thickness / current_price * 100) if current_price > 0 else 0,
                            "compression_score": compression,
                            "breakout_type": breakout_type,
                        }
                        if compression > 70:
                            cloud_compression_bonus = compression * 0.2
                        if direction == BreakoutDirection.LONG and breakout_type in ("strong_breakout_above", "breakout_above"):
                            cloud_compression_bonus += 10.0
                        elif direction == BreakoutDirection.SHORT and breakout_type in ("strong_breakout_below", "breakout_below"):
                            cloud_compression_bonus += 10.0

                # Calculate volatility score
                volatility_score = self.calculate_volatility_score(
                    current_price, atr, volume_ratio, is_breaking_out
                )
                volatility_score = min(100, volatility_score + cloud_compression_bonus)

                if volatility_score < 50:  # Minimum threshold
                    continue

                # Calculate stops based on ATR
                stop_distance = atr * self.config.atr_multiplier_stop
                profit_distance = atr * self.config.atr_multiplier_profit

                if direction == BreakoutDirection.LONG:
                    stop_loss = current_price - stop_distance
                    take_profit = current_price + profit_distance
                else:
                    stop_loss = current_price + stop_distance
                    take_profit = current_price - profit_distance

                signal = BreakoutSignal(
                    symbol=symbol,
                    direction=direction,
                    volatility_score=volatility_score,
                    entry_price=current_price,
                    atr=atr,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicators={
                        "support": support,
                        "resistance": resistance,
                        "atr": atr,
                        "atr_pct": atr_pct,
                        "volume_24h": current_volume,
                        "volume_ratio": volume_ratio,
                        "range_pct": (resistance - support) / current_price * 100 if current_price > 0 else 0,
                        "ichimoku": ichimoku_data,
                        "cloud_compression_bonus": cloud_compression_bonus,
                    },
                    timestamp=int(time.time() * 1000)
                )
                opportunities.append(signal)

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        # Sort by volatility score
        opportunities.sort(key=lambda x: x.volatility_score, reverse=True)
        return opportunities[:6]

    async def calculate_position_size(self, signal: BreakoutSignal) -> float:
        """Calculate position size based on ATR (volatility-adjusted)."""
        try:
            account = await self.client.get_account()
            available = sf(account.available_to_spend)

            if available <= 0:
                return 0.0

            # Risk-based sizing: risk fixed % per trade, adjusted for ATR
            risk_per_trade = available * 0.02  # 2% risk per trade

            # Position size = Risk / (ATR-based stop distance)
            atr_stop_distance = signal.atr * self.config.atr_multiplier_stop
            if atr_stop_distance <= 0:
                return 0.0

            position_value = (risk_per_trade / atr_stop_distance) * signal.entry_price

            # Cap at max position size
            max_notional = available * self.config.position_size_pct * self.config.max_leverage
            position_value = min(position_value, max_notional)

            return position_value / signal.entry_price

        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return 0.0

    async def should_enter(self, signal: BreakoutSignal) -> bool:
        """Check if we should enter this breakout trade."""
        if signal.direction == BreakoutDirection.NONE:
            return False

        if signal.volatility_score < 50:
            return False

        if len(self.active_positions) >= self.config.max_positions:
            return False

        if signal.symbol in self.active_positions:
            return False

        return True

    async def should_exit(self, symbol: str) -> tuple[bool, str]:
        """Check if we should exit this position."""
        pos = self.active_positions.get(symbol)
        if not pos:
            return False, ""

        try:
            price_data = await self.client.get_price(symbol)
            if not price_data:
                return False, ""

            current_price = sf(price_data.mark)

            # Update trailing levels
            if current_price > pos.highest_price:
                pos.highest_price = current_price
            if current_price < pos.lowest_price:
                pos.lowest_price = current_price

            # Time-based exit
            hours_held = (int(time.time() * 1000) - pos.entry_time) / (3600 * 1000)
            if hours_held > self.config.max_hold_hours:
                return True, "time_exit"

            if pos.direction == BreakoutDirection.LONG:
                # Stop loss
                if current_price <= pos.stop_loss:
                    return True, "stop_loss"

                # Take profit
                if current_price >= pos.take_profit:
                    return True, "take_profit"

                # Trailing stop: 2x ATR from highs
                trail_distance = pos.atr * 2
                pos.trailing_stop = pos.highest_price - trail_distance
                if current_price <= pos.trailing_stop and current_price < pos.highest_price * 0.98:
                    return True, "trailing_stop"

            else:  # SHORT
                # Stop loss
                if current_price >= pos.stop_loss:
                    return True, "stop_loss"

                # Take profit
                if current_price <= pos.take_profit:
                    return True, "take_profit"

                # Trailing stop
                trail_distance = pos.atr * 2
                pos.trailing_stop = pos.lowest_price + trail_distance
                if current_price >= pos.trailing_stop and current_price > pos.lowest_price * 1.02:
                    return True, "trailing_stop"

        except Exception as e:
            logger.error(f"Error checking exit for {symbol}: {e}")

        return False, ""

    async def enter_position(self, signal: BreakoutSignal) -> Optional[BreakoutPosition]:
        """Enter a breakout position."""
        if not await self.should_enter(signal):
            return None

        size = await self.calculate_position_size(signal)
        if size <= 0:
            logger.warning(f"Insufficient balance for {signal.symbol}")
            return None

        side = "bid" if signal.direction == BreakoutDirection.LONG else "ask"
        amount_str = f"{size:.6f}"
        order_ids = []

        try:
            result = await self.client.create_market_order(
                symbol=signal.symbol,
                side=side,
                amount=amount_str,
                slippage_percent="0.5",
            )
            order_ids.append(result.get("order_id"))
            logger.info(f"Opened {signal.direction.value} breakout {signal.symbol}: {amount_str} @ {signal.entry_price}")

        except Exception as e:
            logger.error(f"Failed to open position for {signal.symbol}: {e}")
            return None

        position = BreakoutPosition(
            symbol=signal.symbol,
            direction=signal.direction,
            size=size,
            entry_price=signal.entry_price,
            atr=signal.atr,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            entry_time=int(time.time() * 1000),
            order_ids=order_ids,
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price,
        )
        self.active_positions[signal.symbol] = position
        return position

    async def exit_position(self, symbol: str, reason: str) -> bool:
        """Exit a breakout position."""
        pos = self.active_positions.get(symbol)
        if not pos:
            return False

        amount_str = f"{pos.size:.6f}"
        close_side = "ask" if pos.direction == BreakoutDirection.LONG else "bid"

        try:
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent="0.5",
                reduce_only=True,
            )
            logger.info(f"Closed {pos.direction.value} breakout {symbol}: {reason}, order {result.get('order_id')}")
            del self.active_positions[symbol]
            return True

        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return False

    async def run_cycle(self) -> dict:
        """Run one strategy cycle."""
        actions = {"entered": [], "exited": [], "held": [], "errors": []}

        # Check existing positions for exits
        for symbol in list(self.active_positions.keys()):
            try:
                should_exit, reason = await self.should_exit(symbol)
                if should_exit:
                    if await self.exit_position(symbol, reason):
                        actions["exited"].append({"symbol": symbol, "reason": reason})
                    else:
                        actions["errors"].append(f"Failed to exit {symbol}")
                else:
                    actions["held"].append(symbol)
            except Exception as e:
                actions["errors"].append(f"{symbol}: {e}")

        # Scan for new opportunities
        try:
            signals = await self.scan_opportunities()
            for signal in signals:
                if len(self.active_positions) >= self.config.max_positions:
                    break

                pos = await self.enter_position(signal)
                if pos:
                    actions["entered"].append({
                        "symbol": pos.symbol,
                        "direction": pos.direction.value,
                        "size": pos.size,
                        "entry_price": pos.entry_price,
                        "atr": pos.atr,
                        "volatility_score": signal.volatility_score,
                    })
        except Exception as e:
            actions["errors"].append(f"Scan error: {e}")

        return actions

    def get_status(self) -> dict:
        """Get current strategy status."""
        return {
            "strategy_id": self.STRATEGY_ID,
            "strategy_name": self.STRATEGY_NAME,
            "active_positions": len(self.active_positions),
            "positions": [
                {
                    "symbol": p.symbol,
                    "direction": p.direction.value,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "atr": p.atr,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "highest_price": p.highest_price,
                    "lowest_price": p.lowest_price,
                    "entry_time": p.entry_time,
                }
                for p in self.active_positions.values()
            ],
            "config": {
                "atr_multiplier_entry": self.config.atr_multiplier_entry,
                "atr_multiplier_stop": self.config.atr_multiplier_stop,
                "max_positions": self.config.max_positions,
                "position_size_pct": self.config.position_size_pct,
            }
        }
