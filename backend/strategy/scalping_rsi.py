import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pacifica.client import PacificaClient, sf

logger = logging.getLogger(__name__)


class RSISignal(Enum):
    OVERSOLD_BOUNCE = "oversold_bounce"
    OVERBOUGHT_REVERSAL = "overbought_reversal"
    NEUTRAL = "neutral"


@dataclass
class ScalpingRSISignal:
    symbol: str
    signal: RSISignal
    rsi_value: float
    entry_price: float
    stop_loss: float
    take_profit: float
    indicators: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class ScalpingRSIPosition:
    symbol: str
    signal: RSISignal
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    highest_price: float = 0.0
    lowest_price: float = float('inf')


@dataclass
class ScalpingRSIConfig:
    rsi_period: int = 14
    oversold_threshold: float = 30.0
    overbought_threshold: float = 70.0
    candle_interval: str = "5m"
    lookback_minutes: int = 120

    stop_loss_pct: float = 0.6
    take_profit_pct: float = 1.0
    max_hold_minutes: int = 30

    min_volume_24h: float = 200000.0
    max_positions: int = 8
    position_size_pct: float = 0.05
    max_leverage: float = 3.0

    min_rsi_distance: float = 5.0


class ScalpingRSIStrategy:
    """
    Scalping RSI Strategy - Rapid Mean Reversion

    Short timeframe (1m/5m). RSI-based quick entry/exit.
    Enter on RSI oversold (< 30) for long, overbought (> 70) for short.
    Quick mean reversion plays with tight stops.
    """

    STRATEGY_ID = "scalping_rsi"
    STRATEGY_NAME = "Scalping RSI"
    STRATEGY_DESC = "RSI-based scalping strategy for rapid mean reversion trades"
    INDICATORS = ["RSI", "Volume", "Price Action"]

    def __init__(self, client: PacificaClient, config: Optional[ScalpingRSIConfig] = None):
        self.client = client
        self.config = config or ScalpingRSIConfig()
        self.active_positions: dict[str, ScalpingRSIPosition] = {}
        self.signal_history: List[ScalpingRSISignal] = []

    async def calculate_rsi(self, candles: list, period: int = 14) -> float:
        """Calculate RSI for given candles."""
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

        if not gains or not losses:
            return 50.0

        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    async def calculate_ema(self, candles: list, period: int) -> float:
        """Calculate EMA for trend confirmation."""
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

    async def scan_opportunities(self) -> list[ScalpingRSISignal]:
        opportunities = []

        try:
            prices = await self.client.get_prices()
            markets = await self.client.get_markets()
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

                if len(candles) < self.config.rsi_period + 5:
                    continue

                current_price = sf(price_data.mark)

                # Calculate RSI
                rsi = await self.calculate_rsi(candles, self.config.rsi_period)

                # Calculate EMA for trend filter
                ema_20 = await self.calculate_ema(candles, 20)

                volume_24h = sf(price_data.volume_24h)
                if volume_24h < self.config.min_volume_24h:
                    continue

                # Check for oversold or overbought conditions
                signal = None
                signal_strength = 0.0

                if rsi < self.config.oversold_threshold:
                    # Oversold - potential long entry
                    distance = self.config.oversold_threshold - rsi
                    if distance >= self.config.min_rsi_distance:
                        signal = RSISignal.OVERSOLD_BOUNCE
                        signal_strength = min(100, distance * 3)

                        # Trend filter: only take oversold bounces in uptrend
                        if current_price > ema_20:
                            signal_strength += 10

                        stop_loss = current_price * (1 - self.config.stop_loss_pct / 100)
                        take_profit = current_price * (1 + self.config.take_profit_pct / 100)

                elif rsi > self.config.overbought_threshold:
                    # Overbought - potential short entry
                    distance = rsi - self.config.overbought_threshold
                    if distance >= self.config.min_rsi_distance:
                        signal = RSISignal.OVERBOUGHT_REVERSAL
                        signal_strength = min(100, distance * 3)

                        # Trend filter: only take overbought reversals in downtrend
                        if current_price < ema_20:
                            signal_strength += 10

                        stop_loss = current_price * (1 + self.config.stop_loss_pct / 100)
                        take_profit = current_price * (1 - self.config.take_profit_pct / 100)

                if signal:
                    rsi_signal = ScalpingRSISignal(
                        symbol=symbol,
                        signal=signal,
                        rsi_value=rsi,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        indicators={
                            "rsi": rsi,
                            "rsi_period": self.config.rsi_period,
                            "ema_20": ema_20,
                            "volume_24h": volume_24h,
                            "price_above_ema": current_price > ema_20,
                            "signal_strength": signal_strength,
                        },
                        timestamp=int(time.time() * 1000)
                    )
                    opportunities.append(rsi_signal)

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        opportunities.sort(key=lambda x: x.indicators.get("signal_strength", 0), reverse=True)
        return opportunities[:10]

    async def calculate_position_size(self, signal: ScalpingRSISignal) -> float:
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

    async def should_enter(self, signal: ScalpingRSISignal) -> bool:
        if signal.signal == RSISignal.NEUTRAL:
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

            minutes_held = (int(time.time() * 1000) - pos.entry_time) / (60 * 1000)
            if minutes_held > self.config.max_hold_minutes:
                return True, "time_exit"

            if pos.signal == RSISignal.OVERSOLD_BOUNCE:
                if current_price <= pos.stop_loss:
                    return True, "stop_loss"
                if current_price >= pos.take_profit:
                    return True, "take_profit"
            else:  # OVERBOUGHT_REVERSAL (short)
                if current_price >= pos.stop_loss:
                    return True, "stop_loss"
                if current_price <= pos.take_profit:
                    return True, "take_profit"

            # RSI-based exit - recalculate RSI and exit if neutralized
            end_ms = int(time.time() * 1000)
            start_ms = end_ms - (self.config.lookback_minutes * 60 * 1000)
            candles = await self.client.get_candles(
                symbol, self.config.candle_interval, start_ms, end_ms
            )
            if len(candles) >= self.config.rsi_period + 5:
                current_rsi = await self.calculate_rsi(candles, self.config.rsi_period)

                # Exit if RSI normalizes
                if pos.signal == RSISignal.OVERSOLD_BOUNCE and current_rsi > 50:
                    return True, "rsi_normalized"
                if pos.signal == RSISignal.OVERBOUGHT_REVERSAL and current_rsi < 50:
                    return True, "rsi_normalized"

        except Exception as e:
            logger.error(f"Error checking exit for {symbol}: {e}")

        return False, ""

    async def enter_position(self, signal: ScalpingRSISignal) -> Optional[ScalpingRSIPosition]:
        if not await self.should_enter(signal):
            return None

        size = await self.calculate_position_size(signal)
        if size <= 0:
            logger.warning(f"Insufficient balance for {signal.symbol}")
            return None

        # Long for oversold, short for overbought
        side = "bid" if signal.signal == RSISignal.OVERSOLD_BOUNCE else "ask"
        amount_str = f"{size:.6f}"
        order_ids = []

        try:
            result = await self.client.create_market_order(
                symbol=signal.symbol,
                side=side,
                amount=amount_str,
                slippage_percent="0.3",
            )
            order_ids.append(result.get("order_id"))
            logger.info(f"Opened {signal.signal.value} scalp {signal.symbol}: {amount_str} @ {signal.entry_price}")

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

        position = ScalpingRSIPosition(
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
        )
        self.active_positions[signal.symbol] = position
        return position

    async def exit_position(self, symbol: str, reason: str) -> bool:
        pos = self.active_positions.get(symbol)
        if not pos:
            return False

        amount_str = f"{pos.size:.6f}"
        # Reverse the side for exit
        close_side = "ask" if pos.signal == RSISignal.OVERSOLD_BOUNCE else "bid"

        try:
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent="0.3",
                reduce_only=True,
            )
            logger.info(f"Closed {pos.signal.value} scalp {symbol}: {reason}, order {result.get('order_id')}")
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
                        "size": pos.size,
                        "entry_price": pos.entry_price,
                        "rsi": signal.rsi_value,
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
                "oversold_threshold": self.config.oversold_threshold,
                "overbought_threshold": self.config.overbought_threshold,
                "candle_interval": self.config.candle_interval,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
                "max_hold_minutes": self.config.max_hold_minutes,
                "max_positions": self.config.max_positions,
            }
        }
