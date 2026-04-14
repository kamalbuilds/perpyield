import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CloudColor(Enum):
    GREEN = "green"
    RED = "red"
    FLAT = "flat"


class IchimokuTrend(Enum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class IchimokuCloud:
    tenkan_sen: float
    kijun_sen: float
    senkou_span_a: float
    senkou_span_b: float
    chikou_span: float
    cloud_top: float
    cloud_bottom: float
    cloud_color: str
    cloud_thickness: float

    def price_above_cloud(self, price: float) -> bool:
        return price > self.cloud_top

    def price_below_cloud(self, price: float) -> bool:
        return price < self.cloud_bottom

    def price_in_cloud(self, price: float) -> bool:
        return self.cloud_bottom <= price <= self.cloud_top

    def tenkan_above_kijun(self) -> bool:
        return self.tenkan_sen > self.kijun_sen

    def tenkan_below_kijun(self) -> bool:
        return self.tenkan_sen < self.kijun_sen

    def is_thin_cloud(self, price: float, threshold_pct: float = 1.0) -> bool:
        if price <= 0:
            return False
        thickness_pct = (self.cloud_thickness / price) * 100
        return thickness_pct < threshold_pct


@dataclass
class IchimokuSignal:
    trend: IchimokuTrend
    bullish_conditions: int
    bearish_conditions: int
    total_conditions: int
    cloud_color: str
    price_vs_cloud: str
    tk_cross: str
    chikou_vs_price: str
    cloud_thickness_pct: float

    @property
    def is_strong(self) -> bool:
        return self.bullish_conditions == 5 or self.bearish_conditions == 5

    @property
    def direction(self) -> str:
        if self.bullish_conditions >= 3:
            return "bullish"
        elif self.bearish_conditions >= 3:
            return "bearish"
        return "neutral"


class IchimokuCalculator:
    TENKAN_PERIOD = 9
    KIJUN_PERIOD = 26
    SENKOU_B_PERIOD = 52
    CHIKOU_SHIFT = 26
    SENKOU_SHIFT = 26

    def __init__(
        self,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        chikou_shift: int = 26,
    ):
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.chikou_shift = chikou_shift

    @staticmethod
    def _midpoint(candles, period: int) -> float:
        segment = candles[-period:]
        highs = []
        lows = []
        for c in segment:
            h = getattr(c, 'high', None)
            l = getattr(c, 'low', None)
            if h is not None and l is not None:
                try:
                    highs.append(float(h))
                    lows.append(float(l))
                except (ValueError, TypeError):
                    continue
        if not highs or not lows:
            return 0.0
        return (max(highs) + min(lows)) / 2

    def calculate(self, candles: list, current_price: Optional[float] = None) -> Optional[IchimokuCloud]:
        if len(candles) < self.senkou_b_period:
            logger.debug(f"Ichimoku: need {self.senkou_b_period} candles, got {len(candles)}")
            return None

        tenkan = self._midpoint(candles, self.tenkan_period)
        kijun = self._midpoint(candles, self.kijun_period)

        senkou_a = (tenkan + kijun) / 2

        senkou_b = self._midpoint(candles, self.senkou_b_period)

        if current_price is None:
            try:
                current_price = float(candles[-1].close)
            except (ValueError, TypeError, AttributeError):
                return None

        chikou = current_price

        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)
        cloud_thickness = cloud_top - cloud_bottom

        if senkou_a > senkou_b:
            cloud_color = CloudColor.GREEN.value
        elif senkou_a < senkou_b:
            cloud_color = CloudColor.RED.value
        else:
            cloud_color = CloudColor.FLAT.value

        return IchimokuCloud(
            tenkan_sen=tenkan,
            kijun_sen=kijun,
            senkou_span_a=senkou_a,
            senkou_span_b=senkou_b,
            chikou_span=chikou,
            cloud_top=cloud_top,
            cloud_bottom=cloud_bottom,
            cloud_color=cloud_color,
            cloud_thickness=cloud_thickness,
        )

    def generate_signal(self, cloud: IchimokuCloud, price: float) -> IchimokuSignal:
        bullish_conditions = 0
        bearish_conditions = 0

        if cloud.price_above_cloud(price):
            bullish_conditions += 1
            price_vs_cloud = "above"
        elif cloud.price_below_cloud(price):
            bearish_conditions += 1
            price_vs_cloud = "below"
        else:
            price_vs_cloud = "inside"

        if cloud.tenkan_above_kijun():
            bullish_conditions += 1
            tk_cross = "bullish"
        elif cloud.tenkan_below_kijun():
            bearish_conditions += 1
            tk_cross = "bearish"
        else:
            tk_cross = "neutral"

        if cloud.cloud_color == CloudColor.GREEN.value:
            bullish_conditions += 1
        elif cloud.cloud_color == CloudColor.RED.value:
            bearish_conditions += 1

        shifted_close = price
        candles_for_chikou_check = cloud.chikou_span
        if shifted_close > candles_for_chikou_check:
            bullish_conditions += 1
            chikou_vs_price = "above"
        elif shifted_close < candles_for_chikou_check:
            bearish_conditions += 1
            chikou_vs_price = "below"
        else:
            chikou_vs_price = "at"

        if cloud.senkou_span_a > cloud.senkou_span_b:
            bullish_conditions += 1
        elif cloud.senkou_span_a < cloud.senkou_span_b:
            bearish_conditions += 1

        total_conditions = 5

        if bullish_conditions == 5:
            trend = IchimokuTrend.STRONG_BULLISH
        elif bullish_conditions >= 3:
            trend = IchimokuTrend.BULLISH
        elif bearish_conditions == 5:
            trend = IchimokuTrend.STRONG_BEARISH
        elif bearish_conditions >= 3:
            trend = IchimokuTrend.BEARISH
        else:
            trend = IchimokuTrend.NEUTRAL

        cloud_thickness_pct = (cloud.cloud_thickness / price * 100) if price > 0 else 0.0

        return IchimokuSignal(
            trend=trend,
            bullish_conditions=bullish_conditions,
            bearish_conditions=bearish_conditions,
            total_conditions=total_conditions,
            cloud_color=cloud.cloud_color,
            price_vs_cloud=price_vs_cloud,
            tk_cross=tk_cross,
            chikou_vs_price=chikou_vs_price,
            cloud_thickness_pct=cloud_thickness_pct,
        )

    def cloud_breakout_signal(self, cloud: IchimokuCloud, price: float) -> str:
        if cloud.price_above_cloud(price) and cloud.cloud_color == CloudColor.GREEN.value:
            return "strong_breakout_above"
        elif cloud.price_above_cloud(price):
            return "breakout_above"
        elif cloud.price_below_cloud(price) and cloud.cloud_color == CloudColor.RED.value:
            return "strong_breakout_below"
        elif cloud.price_below_cloud(price):
            return "breakout_below"
        elif cloud.price_in_cloud(price):
            if price > (cloud.cloud_bottom + cloud.cloud_thickness * 0.618):
                return "cloud_resistance_near_top"
            elif price < (cloud.cloud_bottom + cloud.cloud_thickness * 0.382):
                return "cloud_support_near_bottom"
            return "inside_cloud"
        return "neutral"

    def cloud_compression(self, cloud: IchimokuCloud, price: float) -> float:
        if price <= 0:
            return 0.0
        thickness_pct = (cloud.cloud_thickness / price) * 100
        compression = max(0.0, min(100.0, 100 - thickness_pct * 10))
        return compression

    def cloud_edge_reversion_targets(self, cloud: IchimokuCloud) -> dict:
        return {
            "cloud_top": cloud.cloud_top,
            "cloud_bottom": cloud.cloud_bottom,
            "cloud_midline": (cloud.cloud_top + cloud.cloud_bottom) / 2,
            "senkou_a": cloud.senkou_span_a,
            "senkou_b": cloud.senkou_span_b,
        }
