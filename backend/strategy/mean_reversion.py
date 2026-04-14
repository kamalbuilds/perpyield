import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pacifica.client import PacificaClient, sf
from indicators.ichimoku import IchimokuCalculator, IchimokuSignal, IchimokuTrend

logger = logging.getLogger(__name__)


class ReversionState(Enum):
    OVERSOLD = "oversold"
    OVERBOUGHT = "overbought"
    NEUTRAL = "neutral"


@dataclass
class ReversionSignal:
    symbol: str
    state: ReversionState
    deviation_score: float  # How far from mean (0-100)
    entry_price: float
    target_price: float  # Mean reversion target
    stop_loss: float
    indicators: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class ReversionPosition:
    symbol: str
    state: ReversionState
    size: float
    entry_price: float
    target_price: float
    stop_loss: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    max_deviation: float = 0.0  # Track how far price went against us


@dataclass
class MeanReversionConfig:
    # Bollinger Bands
    bb_period: int = 20
    bb_std_dev: float = 2.0

    # RSI levels
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    # Mean reversion thresholds
    deviation_entry_threshold: float = 2.0  # Standard deviations
    deviation_exit_threshold: float = 0.5  # Return to mean
    max_deviation: float = 3.5  # Emergency exit

    # Position sizing
    min_volume_24h: float = 50000.0
    max_positions: int = 4
    position_size_pct: float = 0.12
    max_leverage: float = 2.0

    # Lookback for mean calculation
    lookback_hours: int = 48

    # Time in trade
    max_hold_hours: int = 72


class MeanReversionStrategy:
    """
    Mean Reversion Strategy - Pacifica Expert Mode compatible

    Identifies overbought/oversold conditions using Bollinger Bands + RSI.
    Enters when price deviates significantly from mean.
    Exits when price reverts to mean or hits emergency stop.
    """

    STRATEGY_ID = "mean_reversion"
    STRATEGY_NAME = "Mean Reversion"
    STRATEGY_DESC = "Counter-trend strategy using Bollinger Bands + RSI"
    INDICATORS = ["Bollinger Bands", "RSI", "SMA", "Ichimoku Cloud"]

    def __init__(self, client: PacificaClient, config: Optional[MeanReversionConfig] = None):
        self.client = client
        self.config = config or MeanReversionConfig()
        self.active_positions: dict[str, ReversionPosition] = {}
        self.signal_history: List[ReversionSignal] = []
        self.ichimoku = IchimokuCalculator()

    async def calculate_sma(self, candles: list, period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(candles) < period:
            return 0.0

        closes = [sf(c.close) for c in candles[-period:]]
        if not closes or any(c == 0 for c in closes):
            return 0.0

        return sum(closes) / len(closes)

    async def calculate_std_dev(self, candles: list, period: int) -> float:
        """Calculate standard deviation."""
        if len(candles) < period:
            return 0.0

        closes = [sf(c.close) for c in candles[-period:]]
        if not closes or any(c == 0 for c in closes):
            return 0.0

        sma = sum(closes) / len(closes)
        variance = sum((c - sma) ** 2 for c in closes) / len(closes)
        return variance ** 0.5

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

        if not gains or not losses or sum(losses) == 0:
            return 50.0

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def calculate_bollinger_bands(
        self, candles: list, period: int = 20, std_dev: float = 2.0
    ) -> tuple[float, float, float]:
        """Calculate Bollinger Bands (lower, middle, upper)."""
        sma = await self.calculate_sma(candles, period)
        std = await self.calculate_std_dev(candles, period)

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return lower, sma, upper

    def calculate_deviation_score(
        self,
        current_price: float,
        sma: float,
        std: float,
        rsi: float
    ) -> tuple[float, ReversionState]:
        """Calculate how far price deviates from mean (0-100 score)."""
        if std == 0 or sma == 0:
            return 0.0, ReversionState.NEUTRAL

        # Standard deviations from mean
        z_score = (current_price - sma) / std

        # Score based on z-score + RSI confirmation
        score = min(100, abs(z_score) * 25)

        # RSI confirmation boosts score
        if z_score < -2 and rsi < self.config.rsi_oversold:
            score = min(100, score + 20)
            state = ReversionState.OVERSOLD
        elif z_score > 2 and rsi > self.config.rsi_overbought:
            score = min(100, score + 20)
            state = ReversionState.OVERBOUGHT
        else:
            state = ReversionState.NEUTRAL

        return score, state

    async def scan_opportunities(self) -> list[ReversionSignal]:
        """Scan for mean reversion opportunities."""
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
                start_ms = end_ms - (self.config.lookback_hours * 3600 * 1000)
                candles = await self.client.get_candles(symbol, "1h", start_ms, end_ms)

                if len(candles) < self.config.bb_period + 5:
                    continue

                current_price = sf(price_data.mark)

                # Calculate indicators
                bb_lower, bb_middle, bb_upper = await self.calculate_bollinger_bands(
                    candles, self.config.bb_period, self.config.bb_std_dev
                )
                rsi = await self.calculate_rsi(candles, self.config.rsi_period)
                sma = await self.calculate_sma(candles, self.config.bb_period)
                std = await self.calculate_std_dev(candles, self.config.bb_period)

                # Volume check
                volume_24h = sf(price_data.volume_24h)
                if volume_24h < self.config.min_volume_24h:
                    continue

                # Calculate deviation
                deviation_score, state = self.calculate_deviation_score(
                    current_price, sma, std, rsi
                )

                # Only interested in extreme deviations
                if state == ReversionState.NEUTRAL:
                    continue

                # Check if deviation is beyond entry threshold
                z_score = abs((current_price - sma) / std) if std > 0 else 0
                if z_score < self.config.deviation_entry_threshold:
                    continue

                # Generate signal
                if state == ReversionState.OVERSOLD:
                    target_price = sma
                    stop_loss = current_price * 0.96
                    if len(candles) >= 52:
                        cloud = self.ichimoku.calculate(candles, current_price)
                        if cloud and cloud.price_below_cloud(current_price):
                            targets = self.ichimoku.cloud_edge_reversion_targets(cloud)
                            target_price = targets["cloud_bottom"]
                            stop_loss = cloud.cloud_bottom * 0.97
                            z_score += 0.5
                else:
                    target_price = sma
                    stop_loss = current_price * 1.04
                    if len(candles) >= 52:
                        cloud = self.ichimoku.calculate(candles, current_price)
                        if cloud and cloud.price_above_cloud(current_price):
                            targets = self.ichimoku.cloud_edge_reversion_targets(cloud)
                            target_price = targets["cloud_top"]
                            stop_loss = cloud.cloud_top * 1.03
                            z_score += 0.5

                ichimoku_data = {}
                if len(candles) >= 52:
                    cloud = self.ichimoku.calculate(candles, current_price)
                    if cloud:
                        ichimoku_data = {
                            "tenkan_sen": cloud.tenkan_sen,
                            "kijun_sen": cloud.kijun_sen,
                            "cloud_top": cloud.cloud_top,
                            "cloud_bottom": cloud.cloud_bottom,
                            "cloud_color": cloud.cloud_color,
                            "price_vs_cloud": "above" if cloud.price_above_cloud(current_price) else "below" if cloud.price_below_cloud(current_price) else "inside",
                        }

                signal = ReversionSignal(
                    symbol=symbol,
                    state=state,
                    deviation_score=deviation_score,
                    entry_price=current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    indicators={
                        "bb_lower": bb_lower,
                        "bb_middle": bb_middle,
                        "bb_upper": bb_upper,
                        "rsi": rsi,
                        "sma": sma,
                        "std_dev": std,
                        "z_score": z_score,
                        "volume_24h": volume_24h,
                        "ichimoku": ichimoku_data,
                    },
                    timestamp=int(time.time() * 1000)
                )
                opportunities.append(signal)

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        # Sort by deviation score (highest first)
        opportunities.sort(key=lambda x: x.deviation_score, reverse=True)
        return opportunities[:8]

    async def calculate_position_size(self, signal: ReversionSignal) -> float:
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

    async def should_enter(self, signal: ReversionSignal) -> bool:
        """Check if we should enter this mean reversion trade."""
        if signal.state == ReversionState.NEUTRAL:
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

            # Track max deviation
            price_diff = abs(current_price - pos.entry_price) / pos.entry_price
            if price_diff > pos.max_deviation:
                pos.max_deviation = price_diff

            # Emergency exit if deviation grows too much
            if pos.max_deviation > self.config.max_deviation / 100:
                return True, "max_deviation"

            # Time-based exit
            hours_held = (int(time.time() * 1000) - pos.entry_time) / (3600 * 1000)
            if hours_held > self.config.max_hold_hours:
                return True, "time_exit"

            # Check if reverted to mean
            if pos.state == ReversionState.OVERSOLD:  # We went long
                # Exit if price reaches or exceeds target
                if current_price >= pos.target_price:
                    return True, "target_reached"
                # Stop loss
                if current_price <= pos.stop_loss:
                    return True, "stop_loss"

            else:  # OVERBOUGHT - we went short
                # Exit if price reaches or below target
                if current_price <= pos.target_price:
                    return True, "target_reached"
                # Stop loss
                if current_price >= pos.stop_loss:
                    return True, "stop_loss"

        except Exception as e:
            logger.error(f"Error checking exit for {symbol}: {e}")

        return False, ""

    async def enter_position(self, signal: ReversionSignal) -> Optional[ReversionPosition]:
        """Enter a mean reversion position."""
        if not await self.should_enter(signal):
            return None

        size = await self.calculate_position_size(signal)
        if size <= 0:
            logger.warning(f"Insufficient balance for {signal.symbol}")
            return None

        # Long on oversold, short on overbought
        side = "bid" if signal.state == ReversionState.OVERSOLD else "ask"
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
            logger.info(f"Opened {signal.state.value} {signal.symbol}: {amount_str} @ {signal.entry_price}")

        except Exception as e:
            logger.error(f"Failed to open position for {signal.symbol}: {e}")
            return None

        position = ReversionPosition(
            symbol=signal.symbol,
            state=signal.state,
            size=size,
            entry_price=signal.entry_price,
            target_price=signal.target_price,
            stop_loss=signal.stop_loss,
            entry_time=int(time.time() * 1000),
            order_ids=order_ids,
        )
        self.active_positions[signal.symbol] = position
        return position

    async def exit_position(self, symbol: str, reason: str) -> bool:
        """Exit a mean reversion position."""
        pos = self.active_positions.get(symbol)
        if not pos:
            return False

        amount_str = f"{pos.size:.6f}"
        close_side = "ask" if pos.state == ReversionState.OVERSOLD else "bid"

        try:
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent="0.5",
                reduce_only=True,
            )
            logger.info(f"Closed {pos.state.value} {symbol}: {reason}, order {result.get('order_id')}")
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
                        "state": pos.state.value,
                        "size": pos.size,
                        "entry_price": pos.entry_price,
                        "target_price": pos.target_price,
                        "deviation_score": signal.deviation_score,
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
                    "state": p.state.value,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "target_price": p.target_price,
                    "stop_loss": p.stop_loss,
                    "max_deviation": p.max_deviation,
                    "entry_time": p.entry_time,
                }
                for p in self.active_positions.values()
            ],
            "config": {
                "deviation_entry_threshold": self.config.deviation_entry_threshold,
                "max_positions": self.config.max_positions,
                "position_size_pct": self.config.position_size_pct,
                "max_hold_hours": self.config.max_hold_hours,
            }
        }
