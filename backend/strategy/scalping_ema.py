import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

from pacifica.client import PacificaClient, sf

logger = logging.getLogger(__name__)


class EMAState(Enum):
    BULLISH_CROSS = "bullish_cross"
    BEARISH_CROSS = "bearish_cross"
    NEUTRAL = "neutral"


@dataclass
class ScalpingEMASignal:
    symbol: str
    state: EMAState
    cross_strength: float
    entry_price: float
    stop_loss: float
    take_profit: float
    indicators: dict = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class ScalpingEMAPosition:
    symbol: str
    state: EMAState
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: int
    order_ids: list = field(default_factory=list)
    highest_price: float = 0.0
    lowest_price: float = float('inf')


@dataclass
class ScalpingEMAConfig:
    ema_fast_period: int = 8
    ema_slow_period: int = 21
    candle_interval: str = "5m"
    lookback_minutes: int = 120

    stop_loss_pct: float = 0.5
    take_profit_pct: float = 0.8
    max_hold_minutes: int = 30

    min_volume_24h: float = 200000.0
    max_positions: int = 8
    position_size_pct: float = 0.05
    max_leverage: float = 3.0

    cross_min_distance_pct: float = 0.05


class ScalpingEMAStrategy:
    """
    Scalping EMA Strategy - Pacifica Expert Mode

    Very short timeframe (1m/5m). Fast EMA(8) crossing slow EMA(21).
    Quick in/out for small profits with tight stops.
    """

    STRATEGY_ID = "scalping_ema"
    STRATEGY_NAME = "Scalping EMA"
    STRATEGY_DESC = "Scalping with fast EMA(8)/slow EMA(21) crossovers on short timeframes"
    INDICATORS = ["EMA", "Volume", "Ichimoku Cloud"]

    def __init__(self, client: PacificaClient, config: Optional[ScalpingEMAConfig] = None):
        self.client = client
        self.config = config or ScalpingEMAConfig()
        self.active_positions: dict[str, ScalpingEMAPosition] = {}
        self.signal_history: List[ScalpingEMASignal] = []

    async def calculate_ema(self, candles: list, period: int) -> float:
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

    async def calculate_ichimoku(self, candles: list) -> dict:
        if len(candles) < 52:
            return {}

        recent = candles[-52:]

        def midpoint(candle_list, period):
            segment = candle_list[-period:]
            highs = [sf(c.high) for c in segment]
            lows = [sf(c.low) for c in segment]
            if not highs or not lows:
                return 0.0
            return (max(highs) + min(lows)) / 2

        tenkan = midpoint(recent, 9)
        kijun = midpoint(recent, 26)

        senkou_a = (tenkan + kijun) / 2

        period_52 = recent[-52:] if len(recent) >= 52 else recent
        high_52 = max(sf(c.high) for c in period_52)
        low_52 = min(sf(c.low) for c in period_52)
        senkou_b = (high_52 + low_52) / 2

        current_close = sf(candles[-1].close)
        chikou = current_close

        return {
            "tenkan_sen": tenkan,
            "kijun_sen": kijun,
            "senkou_span_a": senkou_a,
            "senkou_span_b": senkou_b,
            "chikou_span": chikou,
            "cloud_top": max(senkou_a, senkou_b),
            "cloud_bottom": min(senkou_a, senkou_b),
            "above_cloud": current_close > max(senkou_a, senkou_b),
            "below_cloud": current_close < min(senkou_a, senkou_b),
        }

    async def scan_opportunities(self) -> list[ScalpingEMASignal]:
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

                if len(candles) < self.config.ema_slow_period + 5:
                    continue

                current_price = sf(price_data.mark)

                ema_fast = await self.calculate_ema(candles, self.config.ema_fast_period)
                ema_slow = await self.calculate_ema(candles, self.config.ema_slow_period)

                if ema_fast == 0 or ema_slow == 0:
                    continue

                distance_pct = abs(ema_fast - ema_slow) / ema_slow * 100
                if distance_pct < self.config.cross_min_distance_pct:
                    continue

                volume_24h = sf(price_data.volume_24h)
                if volume_24h < self.config.min_volume_24h:
                    continue

                ichimoku = await self.calculate_ichimoku(candles)

                if ema_fast > ema_slow:
                    state = EMAState.BULLISH_CROSS
                    ichimoku_confirm = ichimoku.get("above_cloud", False)
                elif ema_fast < ema_slow:
                    state = EMAState.BEARISH_CROSS
                    ichimoku_confirm = ichimoku.get("below_cloud", False)
                else:
                    continue

                cross_strength = min(100, distance_pct * 20)
                if ichimoku_confirm:
                    cross_strength = min(100, cross_strength + 15)

                if state == EMAState.BULLISH_CROSS:
                    stop_loss = current_price * (1 - self.config.stop_loss_pct / 100)
                    take_profit = current_price * (1 + self.config.take_profit_pct / 100)
                else:
                    stop_loss = current_price * (1 + self.config.stop_loss_pct / 100)
                    take_profit = current_price * (1 - self.config.take_profit_pct / 100)

                signal = ScalpingEMASignal(
                    symbol=symbol,
                    state=state,
                    cross_strength=cross_strength,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    indicators={
                        "ema_fast": ema_fast,
                        "ema_slow": ema_slow,
                        "ema_distance_pct": distance_pct,
                        "volume_24h": volume_24h,
                        "ichimoku": ichimoku,
                    },
                    timestamp=int(time.time() * 1000)
                )
                opportunities.append(signal)

            except Exception as e:
                logger.debug(f"Error analyzing {symbol}: {e}")
                continue

        opportunities.sort(key=lambda x: x.cross_strength, reverse=True)
        return opportunities[:10]

    async def calculate_position_size(self, signal: ScalpingEMASignal) -> float:
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

    async def should_enter(self, signal: ScalpingEMASignal) -> bool:
        if signal.state == EMAState.NEUTRAL:
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

            if pos.state == EMAState.BULLISH_CROSS:
                if current_price <= pos.stop_loss:
                    return True, "stop_loss"
                if current_price >= pos.take_profit:
                    return True, "take_profit"
            else:
                if current_price >= pos.stop_loss:
                    return True, "stop_loss"
                if current_price <= pos.take_profit:
                    return True, "take_profit"

            end_ms = int(time.time() * 1000)
            start_ms = end_ms - (self.config.lookback_minutes * 60 * 1000)
            candles = await self.client.get_candles(
                symbol, self.config.candle_interval, start_ms, end_ms
            )
            if len(candles) >= self.config.ema_slow_period + 5:
                ema_fast = await self.calculate_ema(candles, self.config.ema_fast_period)
                ema_slow = await self.calculate_ema(candles, self.config.ema_slow_period)

                if pos.state == EMAState.BULLISH_CROSS and ema_fast < ema_slow:
                    return True, "ema_cross_reversed"
                if pos.state == EMAState.BEARISH_CROSS and ema_fast > ema_slow:
                    return True, "ema_cross_reversed"

        except Exception as e:
            logger.error(f"Error checking exit for {symbol}: {e}")

        return False, ""

    async def enter_position(self, signal: ScalpingEMASignal) -> Optional[ScalpingEMAPosition]:
        if not await self.should_enter(signal):
            return None

        size = await self.calculate_position_size(signal)
        if size <= 0:
            logger.warning(f"Insufficient balance for {signal.symbol}")
            return None

        side = "bid" if signal.state == EMAState.BULLISH_CROSS else "ask"
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
            logger.info(f"Opened {signal.state.value} scalp {signal.symbol}: {amount_str} @ {signal.entry_price}")

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

        position = ScalpingEMAPosition(
            symbol=signal.symbol,
            state=signal.state,
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
        close_side = "ask" if pos.state == EMAState.BULLISH_CROSS else "bid"

        try:
            result = await self.client.create_market_order(
                symbol=symbol,
                side=close_side,
                amount=amount_str,
                slippage_percent="0.3",
                reduce_only=True,
            )
            logger.info(f"Closed {pos.state.value} scalp {symbol}: {reason}, order {result.get('order_id')}")
            del self.active_positions[symbol]
            return True

        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return False

    async def run_cycle(self) -> dict:
        actions = {"entered": [], "exited": [], "held": [], "errors": []}

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
                        "cross_strength": signal.cross_strength,
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
                    "state": p.state.value,
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
                "ema_fast_period": self.config.ema_fast_period,
                "ema_slow_period": self.config.ema_slow_period,
                "candle_interval": self.config.candle_interval,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
                "max_hold_minutes": self.config.max_hold_minutes,
                "max_positions": self.config.max_positions,
            }
        }
