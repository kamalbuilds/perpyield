import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pacifica.client import PacificaClient, sf

logger = logging.getLogger(__name__)


class ConfluenceSignal(Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    STRONG_SELL = "strong_sell"
    SELL = "sell"
    NEUTRAL = "neutral"


@dataclass
class TripleConfluenceSignal:
    symbol: str
    signal: ConfluenceSignal
    confluence_score: int  # 0-3 based on how many indicators align
    entry_price: float
    stop_loss: float
    take_profit: float
    indicators: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class TripleConfluencePosition:
    symbol: str
    signal: ConfluenceSignal
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    highest_price: float = 0.0
    lowest_price: float = float('inf')
    confluence_score: int = 0


@dataclass
class TripleConfluenceConfig:
    # RSI settings
    rsi_period: int = 14
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0

    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Bollinger Bands settings
    bb_period: int = 20
    bb_std_dev: float = 2.0

    # Timeframe and execution
    candle_interval: str = "15m"
    lookback_minutes: int = 240

    # Risk management
    stop_loss_pct: float = 1.5
    take_profit_pct: float = 3.0
    trailing_stop_pct: float = 1.0
    max_hold_hours: int = 24

    # Position sizing
    min_volume_24h: float = 300000.0
    max_positions: int = 5
    position_size_pct: float = 0.08
    max_leverage: float = 4.0

    # Confluence requirements
    min_confluence_score: int = 2  # Need at least 2 of 3 indicators to align


class TripleConfluenceStrategy:
    """
    Triple Confluence Strategy - Multi-Indicator Composite

    Combines 3 powerful indicators for high-confidence entries:
    1. RSI (momentum) - Oversold/overbought conditions
    2. MACD (trend) - Crossovers and histogram direction
    3. Bollinger Bands (volatility) - Band touches and squeeze expansion

    Only enters when at least 2 of 3 indicators align (confluence_score >= 2).
    Higher confluence = higher conviction trades with better R:R.
    """

    STRATEGY_ID = "triple_confluence"
    STRATEGY_NAME = "Triple Confluence"
    STRATEGY_DESC = "Multi-indicator strategy combining RSI, MACD, and Bollinger Bands for high-confidence entries"
    INDICATORS = ["RSI", "MACD", "Bollinger Bands", "Volume"]

    def __init__(self, client: PacificaClient, config: Optional[TripleConfluenceConfig] = None):
        self.client = client
        self.config = config or TripleConfluenceConfig()
        self.active_positions: dict[str, TripleConfluencePosition] = {}
        self.signal_history: List[TripleConfluenceSignal] = []

    async def calculate_rsi(self, candles: list, period: int = 14) -> float:
        """Calculate RSI."""
        if len(candles) < period + 1:
            return 50.0

        closes = [sf(c.close) for c in candles[-(period + 1):]]
        if len(closes) < period + 1:
            return 50.0

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
            return 100.0 if sum(gains) > 0 else 50.0

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def calculate_macd(self, candles: list) -> dict:
        """Calculate MACD, Signal line, and Histogram."""
        if len(candles) < self.config.macd_slow + self.config.macd_signal:
            return {"macd": 0, "signal": 0, "histogram": 0, "trend": "neutral"}

        closes = [sf(c.close) for c in candles]

        # Calculate EMAs
        def calc_ema(data, period):
            multiplier = 2 / (period + 1)
            ema = data[0]
            for price in data[1:]:
                ema = (price - ema) * multiplier + ema
            return ema

        # Get enough data for slow EMA
        ema_fast_list = []
        ema_slow_list = []

        for i in range(self.config.macd_slow, len(closes)):
            slice_fast = closes[i - self.config.macd_fast:i + 1]
            slice_slow = closes[i - self.config.macd_slow:i + 1]
            ema_fast_list.append(calc_ema(slice_fast, self.config.macd_fast))
            ema_slow_list.append(calc_ema(slice_slow, self.config.macd_slow))

        if len(ema_fast_list) < self.config.macd_signal + 1:
            return {"macd": 0, "signal": 0, "histogram": 0, "trend": "neutral"}

        # MACD line
        macd_line = [f - s for f, s in zip(ema_fast_list, ema_slow_list)]

        # Signal line (EMA of MACD)
        signal_line = calc_ema(macd_line[-self.config.macd_signal:], self.config.macd_signal)

        # Current MACD
        current_macd = macd_line[-1]
        histogram = current_macd - signal_line

        # Determine trend
        prev_macd = macd_line[-2] if len(macd_line) > 1 else current_macd
        prev_signal = calc_ema(macd_line[-(self.config.macd_signal + 1):-1], self.config.macd_signal) if len(macd_line) > 1 else signal_line

        trend = "neutral"
        if current_macd > signal_line and prev_macd <= prev_signal:
            trend = "bullish_cross"
        elif current_macd < signal_line and prev_macd >= prev_signal:
            trend = "bearish_cross"
        elif current_macd > signal_line:
            trend = "bullish"
        elif current_macd < signal_line:
            trend = "bearish"

        return {
            "macd": current_macd,
            "signal": signal_line,
            "histogram": histogram,
            "trend": trend,
            "histogram_rising": histogram > (macd_line[-2] - calc_ema(macd_line[-(self.config.macd_signal + 1):-1], self.config.macd_signal)) if len(macd_line) > 1 else False
        }

    async def calculate_bollinger_bands(self, candles: list) -> dict:
        """Calculate Bollinger Bands."""
        if len(candles) < self.config.bb_period:
            return {"upper": 0, "middle": 0, "lower": 0, "squeeze": False}

        closes = [sf(c.close) for c in candles[-self.config.bb_period:]]

        sma = sum(closes) / len(closes)
        variance = sum((c - sma) ** 2 for c in closes) / len(closes)
        std_dev = variance ** 0.5

        upper = sma + (std_dev * self.config.bb_std_dev)
        lower = sma - (std_dev * self.config.bb_std_dev)

        current_price = closes[-1]

        # Detect squeeze (low volatility)
        bandwidth = (upper - lower) / sma * 100
        squeeze = bandwidth < 5  # Less than 5% bandwidth is considered squeeze

        # Position relative to bands
        percent_b = (current_price - lower) / (upper - lower) if upper != lower else 0.5

        return {
            "upper": upper,
            "middle": sma,
            "lower": lower,
            "bandwidth": bandwidth,
            "squeeze": squeeze,
            "percent_b": percent_b,
            "near_upper": percent_b > 0.9,
            "near_lower": percent_b < 0.1,
            "above_upper": current_price > upper,
            "below_lower": current_price < lower,
        }

    def calculate_confluence(self, rsi: float, macd: dict, bb: dict) -> tuple[ConfluenceSignal, int]:
        """
        Calculate confluence score (0-3) based on indicator alignment.
        Returns signal direction and confluence score.
        """
        bullish_signals = 0
        bearish_signals = 0

        # RSI signals
        if rsi < self.config.rsi_oversold:
            bullish_signals += 1
        elif rsi > self.config.rsi_overbought:
            bearish_signals += 1

        # MACD signals
        if macd["trend"] in ["bullish", "bullish_cross"]:
            bullish_signals += 1
        elif macd["trend"] in ["bearish", "bearish_cross"]:
            bearish_signals += 1

        # Bollinger Bands signals
        if bb.get("near_lower", False):
            bullish_signals += 1
        elif bb.get("near_upper", False):
            bearish_signals += 1

        # Determine signal
        if bullish_signals >= self.config.min_confluence_score and bullish_signals > bearish_signals:
            score = bullish_signals
            if score >= 3:
                return ConfluenceSignal.STRONG_BUY, score
            return ConfluenceSignal.BUY, score

        if bearish_signals >= self.config.min_confluence_score and bearish_signals > bullish_signals:
            score = bearish_signals
            if score >= 3:
                return ConfluenceSignal.STRONG_SELL, score
            return ConfluenceSignal.SELL, score

        return ConfluenceSignal.NEUTRAL, max(bullish_signals, bearish_signals)

    async def scan_opportunities(self) -> list[TripleConfluenceSignal]:
        opportunities = []

        try:
            prices = await self.client.get_prices()
        except Exception as e:
            logger.error(f"Failed to fetch market data: {e}")
            return opportunities

        for price_data in prices:
            symbol = price_data.symbol

            if symbol in self.active_positions:
                continue

            try:
                end_ms = int(time.time() * 1000)
                start_ms = end_ms - (self.config.lookback_minutes * 60 * 1000)
                candles = await self.client.get_candles(
                    symbol, self.config.candle_interval, start_ms, end_ms
                )

                min_candles = max(
                    self.config.rsi_period + 1,
                    self.config.macd_slow + self.config.macd_signal,
                    self.config.bb_period
                )

                if len(candles) < min_candles + 5:
                    continue

                current_price = sf(price_data.mark)
                volume_24h = sf(price_data.volume_24h)

                if volume_24h < self.config.min_volume_24h:
                    continue

                # Calculate all indicators
                rsi = await self.calculate_rsi(candles, self.config.rsi_period)
                macd = await self.calculate_macd(candles)
                bb = await self.calculate_bollinger_bands(candles)

                # Calculate confluence
                signal, confluence_score = self.calculate_confluence(rsi, macd, bb)

                if signal in [ConfluenceSignal.NEUTRAL] or confluence_score < self.config.min_confluence_score:
                    continue

                # Calculate entry, stop, and take profit
                if signal in [ConfluenceSignal.BUY, ConfluenceSignal.STRONG_BUY]:
                    stop_loss = current_price * (1 - self.config.stop_loss_pct / 100)
                    take_profit = current_price * (1 + self.config.take_profit_pct / 100)
                else:  # SELL or STRONG_SELL
                    stop_loss = current_price * (1 + self.config.stop_loss_pct / 100)
                    take_profit = current_price * (1 - self.config.take_profit_pct / 100)

                # Bonus for squeeze (explosive moves expected)
                squeeze_bonus = 5 if bb.get("squeeze", False) else 0

                confluence_signal = TripleConfluenceSignal(
                    symbol=symbol,
                    signal=signal,
                    confluence_score=confluence_score,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicators={
                        "rsi": rsi,
                        "macd": macd,
                        "bollinger_bands": bb,
                        "volume_24h": volume_24h,
                        "squeeze": bb.get("squeeze", False),
                        "signal_quality": confluence_score * 25 + squeeze_bonus,
                    },
                    timestamp=int(time.time() * 1000)
                )
                opportunities.append(confluence_signal)

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        # Sort by signal quality (confluence score * 25 + bonuses)
        opportunities.sort(
            key=lambda x: x.indicators.get("signal_quality", 0),
            reverse=True
        )
        return opportunities[:8]

    async def calculate_position_size(self, signal: TripleConfluenceSignal) -> float:
        try:
            account = await self.client.get_account()
            available = sf(account.available_to_spend)

            if available <= 0:
                return 0.0

            # Increase size for high confluence (stronger conviction)
            size_multiplier = 1.0 + (signal.confluence_score - 2) * 0.3  # 1.0x, 1.3x, 1.6x

            max_notional = available * self.config.position_size_pct * size_multiplier
            leveraged_notional = max_notional * self.config.max_leverage
            return leveraged_notional / signal.entry_price

        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return 0.0

    async def should_enter(self, signal: TripleConfluenceSignal) -> bool:
        if signal.signal == ConfluenceSignal.NEUTRAL:
            return False

        if signal.confluence_score < self.config.min_confluence_score:
            return False

        if len(self.active_positions) >= self.config.max_positions:
            return False

        if signal.symbol in self.active_positions:
            return False

        return True

    async def should_exit(self, symbol: str) -> tuple[bool, str]:
        pos = self.active_positions.get(symbol)
        if not pos:
            return False, ""

        try:
            price_data = await self.client.get_price(symbol)
            if not price_data:
                return False, ""

            current_price = sf(price_data.mark)

            if current_price > pos.highest_price:
                pos.highest_price = current_price
            if current_price < pos.lowest_price:
                pos.lowest_price = current_price

            hours_held = (int(time.time() * 1000) - pos.entry_time) / (3600 * 1000)
            if hours_held > self.config.max_hold_hours:
                return True, "time_exit"

            # Check stop loss and take profit
            if pos.signal in [ConfluenceSignal.BUY, ConfluenceSignal.STRONG_BUY]:
                if current_price <= pos.stop_loss:
                    return True, "stop_loss"
                if current_price >= pos.take_profit:
                    return True, "take_profit"

                # Trailing stop
                price_range = pos.take_profit - pos.entry_price
                if current_price > pos.entry_price + price_range * 0.5:
                    trail_stop = pos.highest_price * (1 - self.config.trailing_stop_pct / 100)
                    if current_price < trail_stop:
                        return True, "trailing_stop"
            else:  # SELL positions
                if current_price >= pos.stop_loss:
                    return True, "stop_loss"
                if current_price <= pos.take_profit:
                    return True, "take_profit"

                # Trailing stop for shorts
                price_range = pos.entry_price - pos.take_profit
                if current_price < pos.entry_price - price_range * 0.5:
                    trail_stop = pos.lowest_price * (1 + self.config.trailing_stop_pct / 100)
                    if current_price > trail_stop:
                        return True, "trailing_stop"

            # Re-calculate indicators for early exit if confluence breaks
            end_ms = int(time.time() * 1000)
            start_ms = end_ms - (self.config.lookback_minutes * 60 * 1000)
            candles = await self.client.get_candles(
                symbol, self.config.candle_interval, start_ms, end_ms
            )

            min_candles = max(
                self.config.rsi_period + 1,
                self.config.macd_slow + self.config.macd_signal,
                self.config.bb_period
            )

            if len(candles) >= min_candles:
                rsi = await self.calculate_rsi(candles, self.config.rsi_period)
                macd = await self.calculate_macd(candles)
                bb = await self.calculate_bollinger_bands(candles)

                new_signal, new_score = self.calculate_confluence(rsi, macd, bb)

                # Exit if signal completely reversed with high confluence
                if pos.signal in [ConfluenceSignal.BUY, ConfluenceSignal.STRONG_BUY]:
                    if new_signal in [ConfluenceSignal.STRONG_SELL] and new_score >= 2:
                        return True, "confluence_reversed"
                elif pos.signal in [ConfluenceSignal.SELL, ConfluenceSignal.STRONG_SELL]:
                    if new_signal in [ConfluenceSignal.STRONG_BUY] and new_score >= 2:
                        return True, "confluence_reversed"

        except Exception as e:
            logger.error(f"Error checking exit for {symbol}: {e}")

        return False, ""

    async def enter_position(self, signal: TripleConfluenceSignal) -> Optional[TripleConfluencePosition]:
        if not await self.should_enter(signal):
            return None

        size = await self.calculate_position_size(signal)
        if size <= 0:
            logger.warning(f"Insufficient balance for {signal.symbol}")
            return None

        # Determine side
        if signal.signal in [ConfluenceSignal.BUY, ConfluenceSignal.STRONG_BUY]:
            side = "bid"
        else:
            side = "ask"

        amount_str = f"{size:.6f}"
        order_ids = []

        try:
            result = await self.client.create_market_order(
                symbol=signal.symbol,
                side=side,
                amount=amount_str,
                slippage_percent="0.4",
            )
            order_ids.append(result.get("order_id"))
            logger.info(f"Opened {signal.signal.value} confluence {signal.symbol}: {amount_str} @ {signal.entry_price}")

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

        position = TripleConfluencePosition(
            symbol=signal.symbol,
            signal=signal.signal,
            size=size,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            entry_time=int(time.time() * 1000),
            order_ids=order_ids,
            highest_price=signal.entry_price,
            lowest_price=signal.entry_price,
            confluence_score=signal.confluence_score,
        )
        self.active_positions[signal.symbol] = position
        return position

    async def exit_position(self, symbol: str, reason: str) -> bool:
        pos = self.active_positions.get(symbol)
        if not pos:
            return False

        amount_str = f"{pos.size:.6f}"

        # Reverse side for exit
        if pos.signal in [ConfluenceSignal.BUY, ConfluenceSignal.STRONG_BUY]:
            close_side = "ask"
        else:
            close_side = "bid"

        try:
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent="0.4",
                reduce_only=True,
            )
            logger.info(f"Closed {pos.signal.value} confluence {symbol}: {reason}, order {result.get('order_id')}")
            del self.active_positions[symbol]
            return True

        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return False

    async def run_cycle(self) -> dict:
        actions = {"entered": [], "exited": [], "held": [], "errors": []}

        # Check exits first
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

        # Scan for new entries
        try:
            signals = await self.scan_opportunities()
            for signal in signals:
                if len(self.active_positions) >= self.config.max_positions:
                    break

                pos = await self.enter_position(signal)
                if pos:
                    actions["entered"].append({
                        "symbol": pos.symbol,
                        "signal": pos.signal.value,
                        "confluence_score": pos.confluence_score,
                        "size": pos.size,
                        "entry_price": pos.entry_price,
                    })
        except Exception as e:
            actions["errors"].append(f"Scan error: {e}")

        return actions

    def get_status(self) -> dict:
        return {
            "strategy_id": self.STRATEGY_ID,
            "strategy_name": self.STRATEGY_NAME,
            "active_positions": len(self.active_positions),
            "positions": [
                {
                    "symbol": p.symbol,
                    "signal": p.signal.value,
                    "confluence_score": p.confluence_score,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "entry_time": p.entry_time,
                    "highest_price": p.highest_price,
                    "lowest_price": p.lowest_price,
                }
                for p in self.active_positions.values()
            ],
            "config": {
                "rsi_period": self.config.rsi_period,
                "rsi_oversold": self.config.rsi_oversold,
                "rsi_overbought": self.config.rsi_overbought,
                "candle_interval": self.config.candle_interval,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
                "max_positions": self.config.max_positions,
                "min_confluence_score": self.config.min_confluence_score,
            }
        }
