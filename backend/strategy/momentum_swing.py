import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pacifica.client import PacificaClient, sf
from indicators.ichimoku import IchimokuCalculator, IchimokuSignal, IchimokuTrend

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class MomentumSignal:
    symbol: str
    direction: TrendDirection
    strength: float  # 0-100 momentum score
    entry_price: float
    stop_loss: float
    take_profit: float
    indicators: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class MomentumPosition:
    symbol: str
    direction: TrendDirection
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    trailing_stop: float = 0.0


@dataclass
class MomentumConfig:
    # Trend detection
    ema_fast_period: int = 9
    ema_slow_period: int = 21
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Entry/Exit
    momentum_threshold: float = 60.0  # Minimum momentum score to enter
    min_volume_24h: float = 100000.0
    max_positions: int = 5
    position_size_pct: float = 0.15

    # Risk Management
    stop_loss_pct: float = 3.0
    take_profit_pct: float = 6.0
    trailing_stop_pct: float = 2.0
    max_leverage: float = 2.0

    # Timeframes
    trend_lookback_hours: int = 24
    entry_confirmation_bars: int = 2


class MomentumSwingStrategy:
    """
    Momentum Swing Strategy - Pacifica Expert Mode compatible

    Scans for trending assets using EMA crossover + RSI + MACD confirmation.
    Enters on momentum confirmation with tight risk management.
    Uses trailing stops to capture extended moves.
    """

    STRATEGY_ID = "momentum_swing"
    STRATEGY_NAME = "Momentum Swing"
    STRATEGY_DESC = "Trend-following strategy using EMA crossover + RSI + MACD"
    INDICATORS = ["EMA", "RSI", "MACD", "Ichimoku Cloud"]

    def __init__(self, client: PacificaClient, config: Optional[MomentumConfig] = None):
        self.client = client
        self.config = config or MomentumConfig()
        self.active_positions: dict[str, MomentumPosition] = {}
        self.signal_history: List[MomentumSignal] = []
        self.ichimoku = IchimokuCalculator()

    async def calculate_ema(self, candles: list, period: int) -> float:
        """Calculate EMA from candle closes."""
        if len(candles) < period:
            return 0.0

        closes = [sf(c.close) for c in candles[-period:]]
        if not closes or any(c == 0 for c in closes):
            return 0.0

        multiplier = 2 / (period + 1)
        ema = closes[0]
        for close in closes[1:]:
            ema = (close - ema) * multiplier + ema
        return ema

    async def calculate_rsi(self, candles: list, period: int = 14) -> float:
        """Calculate RSI from candle closes."""
        if len(candles) < period + 1:
            return 50.0

        closes = [sf(c.close) for c in candles[-(period + 1):]]
        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        if not gains or not losses:
            return 50.0

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_momentum_score(
        self,
        ema_fast: float,
        ema_slow: float,
        rsi: float,
        price_change_24h: float
    ) -> tuple[float, TrendDirection]:
        """Calculate overall momentum score (0-100) and direction."""
        score = 0.0
        direction = TrendDirection.NEUTRAL

        # EMA trend (40 points max)
        if ema_fast > ema_slow:
            ema_diff = (ema_fast - ema_slow) / ema_slow
            score += min(40, 40 * ema_diff * 100)
            direction = TrendDirection.BULLISH
        elif ema_fast < ema_slow:
            ema_diff = (ema_slow - ema_fast) / ema_fast
            score += min(40, 40 * ema_diff * 100)
            direction = TrendDirection.BEARISH

        # RSI momentum (30 points max)
        if direction == TrendDirection.BULLISH and rsi > 50:
            score += min(30, (rsi - 50) * 0.6)
        elif direction == TrendDirection.BEARISH and rsi < 50:
            score += min(30, (50 - rsi) * 0.6)

        # Price change (30 points max)
        score += min(30, abs(price_change_24h) * 3)

        return min(100, score), direction

    async def scan_opportunities(self) -> list[MomentumSignal]:
        """Scan all markets for momentum opportunities."""
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
                # Get recent candles for analysis
                end_ms = int(time.time() * 1000)
                start_ms = end_ms - (self.config.trend_lookback_hours * 3600 * 1000)
                candles = await self.client.get_candles(symbol, "1h", start_ms, end_ms)

                if len(candles) < max(self.config.ema_slow_period, self.config.rsi_period) + 5:
                    continue

                current_price = sf(price_data.mark)
                oracle_price = sf(price_data.oracle)

                # Calculate indicators
                ema_fast = await self.calculate_ema(candles, self.config.ema_fast_period)
                ema_slow = await self.calculate_ema(candles, self.config.ema_slow_period)
                rsi = await self.calculate_rsi(candles, self.config.rsi_period)

                # 24h price change
                first_price = sf(candles[0].close) if candles else current_price
                price_change_24h = ((current_price - first_price) / first_price) * 100 if first_price > 0 else 0

                # Calculate momentum score
                momentum_score, direction = self.calculate_momentum_score(
                    ema_fast, ema_slow, rsi, price_change_24h
                )

                ichimoku_data = {}
                ichimoku_breakout_bonus = 0.0
                if len(candles) >= 52:
                    cloud = self.ichimoku.calculate(candles, current_price)
                    if cloud:
                        ichimoku_signal = self.ichimoku.generate_signal(cloud, current_price)
                        breakout = self.ichimoku.cloud_breakout_signal(cloud, current_price)
                        ichimoku_data = {
                            "tenkan_sen": cloud.tenkan_sen,
                            "kijun_sen": cloud.kijun_sen,
                            "cloud_top": cloud.cloud_top,
                            "cloud_bottom": cloud.cloud_bottom,
                            "cloud_color": cloud.cloud_color,
                            "price_vs_cloud": ichimoku_signal.price_vs_cloud,
                            "tk_cross": ichimoku_signal.tk_cross,
                            "breakout": breakout,
                            "ichimoku_trend": ichimoku_signal.trend.value,
                        }
                        if direction == TrendDirection.BULLISH and breakout in ("strong_breakout_above", "breakout_above"):
                            ichimoku_breakout_bonus = 15.0
                        elif direction == TrendDirection.BEARISH and breakout in ("strong_breakout_below", "breakout_below"):
                            ichimoku_breakout_bonus = 15.0
                        if ichimoku_signal.bullish_conditions >= 3 and direction == TrendDirection.BULLISH:
                            ichimoku_breakout_bonus += 10.0
                        elif ichimoku_signal.bearish_conditions >= 3 and direction == TrendDirection.BEARISH:
                            ichimoku_breakout_bonus += 10.0

                momentum_score = min(100, momentum_score + ichimoku_breakout_bonus)

                # Volume check
                volume_24h = sf(price_data.volume_24h)
                if volume_24h < self.config.min_volume_24h:
                    continue

                # Minimum momentum threshold
                if momentum_score < self.config.momentum_threshold:
                    continue

                # Generate signal
                if direction == TrendDirection.BULLISH:
                    stop_loss = current_price * (1 - self.config.stop_loss_pct / 100)
                    take_profit = current_price * (1 + self.config.take_profit_pct / 100)
                else:
                    stop_loss = current_price * (1 + self.config.stop_loss_pct / 100)
                    take_profit = current_price * (1 - self.config.take_profit_pct / 100)

                signal = MomentumSignal(
                    symbol=symbol,
                    direction=direction,
                    strength=momentum_score,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicators={
                        "ema_fast": ema_fast,
                        "ema_slow": ema_slow,
                        "rsi": rsi,
                        "price_change_24h": price_change_24h,
                        "volume_24h": volume_24h,
                        "ichimoku": ichimoku_data,
                        "ichimoku_breakout_bonus": ichimoku_breakout_bonus,
                    },
                    timestamp=int(time.time() * 1000)
                )
                opportunities.append(signal)

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        # Sort by momentum strength
        opportunities.sort(key=lambda x: x.strength, reverse=True)
        return opportunities[:10]

    async def calculate_position_size(self, signal: MomentumSignal) -> float:
        """Calculate position size based on account equity."""
        try:
            account = await self.client.get_account()
            available = sf(account.available_to_spend)

            if available <= 0:
                return 0.0

            max_notional = available * self.config.position_size_pct
            leveraged_notional = max_notional * self.config.max_leverage
            return leveraged_notional / signal.entry_price

        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return 0.0

    async def should_enter(self, signal: MomentumSignal) -> bool:
        """Check if we should enter this momentum trade."""
        if signal.strength < self.config.momentum_threshold:
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

            # Update trailing high/low
            if current_price > pos.highest_price:
                pos.highest_price = current_price
            if current_price < pos.lowest_price:
                pos.lowest_price = current_price

            # Calculate trailing stop
            if pos.direction == TrendDirection.BULLISH:
                pos.trailing_stop = pos.highest_price * (1 - self.config.trailing_stop_pct / 100)

                # Check stop loss
                if current_price <= pos.stop_loss:
                    return True, "stop_loss"

                # Check trailing stop
                if current_price <= pos.trailing_stop and current_price < pos.highest_price * 0.98:
                    return True, "trailing_stop"

                # Check take profit
                if current_price >= pos.take_profit:
                    return True, "take_profit"

            else:  # BEARISH (short)
                pos.trailing_stop = pos.lowest_price * (1 + self.config.trailing_stop_pct / 100)

                # Check stop loss
                if current_price >= pos.stop_loss:
                    return True, "stop_loss"

                # Check trailing stop
                if current_price >= pos.trailing_stop and current_price > pos.lowest_price * 1.02:
                    return True, "trailing_stop"

                # Check take profit
                if current_price <= pos.take_profit:
                    return True, "take_profit"

        except Exception as e:
            logger.error(f"Error checking exit for {symbol}: {e}")

        return False, ""

    async def enter_position(self, signal: MomentumSignal) -> Optional[MomentumPosition]:
        """Enter a momentum position."""
        if not await self.should_enter(signal):
            return None

        size = await self.calculate_position_size(signal)
        if size <= 0:
            logger.warning(f"Insufficient balance for {signal.symbol}")
            return None

        side = "bid" if signal.direction == TrendDirection.BULLISH else "ask"
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
            logger.info(f"Opened {signal.direction.value} {signal.symbol}: {amount_str} @ {signal.entry_price}")

            # Set stop loss and take profit
            try:
                await self.client.set_tpsl(
                    symbol=signal.symbol,
                    side=side,
                    stop_loss={"stop_price": str(signal.stop_loss)},
                    take_profit={"stop_price": str(signal.take_profit)}
                )
            except Exception as e:
                logger.warning(f"Failed to set TPSL for {signal.symbol}: {e}")

        except Exception as e:
            logger.error(f"Failed to open position for {signal.symbol}: {e}")
            return None

        position = MomentumPosition(
            symbol=signal.symbol,
            direction=signal.direction,
            size=size,
            entry_price=signal.entry_price,
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
        """Exit a momentum position."""
        pos = self.active_positions.get(symbol)
        if not pos:
            return False

        amount_str = f"{pos.size:.6f}"
        close_side = "ask" if pos.direction == TrendDirection.BULLISH else "bid"

        try:
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent="0.5",
                reduce_only=True,
            )
            logger.info(f"Closed {pos.direction.value} {symbol}: {reason}, order {result.get('order_id')}")
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
                        "momentum_score": signal.strength,
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
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "highest_price": p.highest_price,
                    "lowest_price": p.lowest_price,
                    "entry_time": p.entry_time,
                }
                for p in self.active_positions.values()
            ],
            "config": {
                "momentum_threshold": self.config.momentum_threshold,
                "max_positions": self.config.max_positions,
                "position_size_pct": self.config.position_size_pct,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
            }
        }
