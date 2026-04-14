import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pacifica.client import PacificaClient, sf
from strategy.funding_scanner import FundingScanner

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    NEUTRAL = "neutral"


@dataclass
class MarketMetrics:
    avg_funding_rate: float = 0.0
    funding_rate_count: int = 0
    positive_funding_pct: float = 0.0
    volatility_index: float = 0.0
    trend_strength: float = 0.0
    range_bound_score: float = 0.0
    top_funding_symbols: list = field(default_factory=list)
    high_volatility_symbols: list = field(default_factory=list)
    trending_symbols: list = field(default_factory=list)
    timestamp: int = 0


class MarketAnalyzer:
    FUNDING_HIGH_THRESHOLD = 0.0005
    VOLATILITY_HIGH_THRESHOLD = 5.0
    TREND_STRONG_THRESHOLD = 60.0
    BB_WIDTH_NARROW_THRESHOLD = 0.03

    def __init__(self, client: PacificaClient):
        self.client = client
        self.scanner = FundingScanner(client, min_apy=0.0)
        self._last_regime: Optional[MarketRegime] = None
        self._regime_history: list[dict] = []

    async def _fetch_funding_metrics(self) -> tuple[float, int, float, list]:
        try:
            all_rates = await self.scanner.fetch_all_funding_rates()
            if not all_rates:
                return 0.0, 0, 0.0, []

            rates = [r["funding_rate"] for r in all_rates]
            avg_rate = sum(rates) / len(rates) if rates else 0.0
            positive_pct = (sum(1 for r in rates if r > 0) / len(rates) * 100) if rates else 0.0

            ranked = sorted(all_rates, key=lambda x: abs(x["funding_rate"]), reverse=True)
            top_symbols = [
                {
                    "symbol": r["symbol"],
                    "funding_rate": r["funding_rate"],
                    "apy": FundingScanner.rate_to_apy(r["funding_rate"]),
                    "volume_24h": r["volume_24h"],
                }
                for r in ranked[:5]
                if abs(r["funding_rate"]) > 0
            ]

            return avg_rate, len(rates), positive_pct, top_symbols
        except Exception as e:
            logger.error(f"Failed to fetch funding metrics: {e}")
            return 0.0, 0, 0.0, []

    async def _analyze_symbol_volatility(self, symbol: str, candles: list) -> Optional[dict]:
        if len(candles) < 20:
            return None

        closes = [sf(c.close) for c in candles[-20:]]
        if any(c == 0 for c in closes):
            return None

        returns = [(closes[i] - closes[i - 1]) / closes[i - 1] * 100 for i in range(1, len(closes))]
        if not returns:
            return None

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5

        sma = sum(closes) / len(closes)
        diffs = [(c - sma) ** 2 for c in closes]
        std = (sum(diffs) / len(diffs)) ** 0.5
        bb_width = (std * 4) / sma * 100 if sma > 0 else 0.0

        ema9 = closes[-1]
        multiplier = 2 / 10
        for c in closes[-9:]:
            ema9 = (c - ema9) * multiplier + ema9

        ema21 = closes[-1]
        multiplier21 = 2 / 22
        for c in closes[-21:] if len(closes) >= 21 else closes:
            ema21 = (c - ema21) * multiplier21 + ema21

        trend_strength = min(100, abs(ema9 - ema21) / sma * 100 * 20) if sma > 0 else 0.0

        price_change_pct = abs((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] > 0 else 0.0
        if ema9 > ema21 and price_change_pct > 1.5:
            trend_direction = "bullish"
        elif ema9 < ema21 and price_change_pct > 1.5:
            trend_direction = "bearish"
        else:
            trend_direction = "neutral"

        return {
            "symbol": symbol,
            "volatility": volatility,
            "bb_width": bb_width,
            "trend_strength": trend_strength,
            "trend_direction": trend_direction,
            "ema9": ema9,
            "ema21": ema21,
            "sma": sma,
        }

    async def _fetch_volatility_and_trend(self) -> tuple[float, float, float, list, list]:
        try:
            prices = await self.client.get_prices()
            if not prices:
                return 0.0, 0.0, 0.0, [], []

            end_ms = int(time.time() * 1000)
            start_ms = end_ms - 48 * 3600 * 1000

            total_volatility = 0.0
            total_trend = 0.0
            total_bb_width = 0.0
            analyzed = 0
            high_vol_symbols = []
            trending_symbols = []

            for p in prices[:20]:
                try:
                    candles = await self.client.get_candles(p.symbol, "1h", start_ms, end_ms)
                    result = await self._analyze_symbol_volatility(p.symbol, candles)
                    if result is None:
                        continue

                    analyzed += 1
                    total_volatility += result["volatility"]
                    total_trend += result["trend_strength"]
                    total_bb_width += result["bb_width"]

                    if result["volatility"] > self.VOLATILITY_HIGH_THRESHOLD:
                        high_vol_symbols.append({
                            "symbol": result["symbol"],
                            "volatility": round(result["volatility"], 2),
                            "trend_direction": result["trend_direction"],
                        })

                    if result["trend_strength"] > self.TREND_STRONG_THRESHOLD:
                        trending_symbols.append({
                            "symbol": result["symbol"],
                            "trend_strength": round(result["trend_strength"], 2),
                            "trend_direction": result["trend_direction"],
                        })
                except Exception:
                    continue

            if analyzed == 0:
                return 0.0, 0.0, 0.0, [], []

            avg_volatility = total_volatility / analyzed
            avg_trend = total_trend / analyzed
            avg_bb_width = total_bb_width / analyzed

            volatility_index = min(100, avg_volatility * 10)
            trend_strength = min(100, avg_trend)
            range_bound_score = min(100, max(0, 100 - avg_bb_width * 200))

            return volatility_index, trend_strength, range_bound_score, high_vol_symbols, trending_symbols

        except Exception as e:
            logger.error(f"Failed to fetch volatility/trend data: {e}")
            return 0.0, 0.0, 0.0, [], []

    async def analyze_market(self) -> dict:
        avg_funding, funding_count, positive_pct, top_funding = await self._fetch_funding_metrics()
        volatility_idx, trend_str, range_score, high_vol_syms, trending_syms = await self._fetch_volatility_and_trend()

        metrics = MarketMetrics(
            avg_funding_rate=avg_funding,
            funding_rate_count=funding_count,
            positive_funding_pct=positive_pct,
            volatility_index=volatility_idx,
            trend_strength=trend_str,
            range_bound_score=range_score,
            top_funding_symbols=top_funding,
            high_volatility_symbols=high_vol_syms,
            trending_symbols=trending_syms,
            timestamp=int(time.time() * 1000),
        )

        regime, confidence, reasoning = self._determine_regime(metrics)
        recommended, rec_confidence = self._recommend_strategy_for_regime(regime, metrics)

        previous_regime = self._last_regime
        self._last_regime = regime

        regime_changed = previous_regime is not None and previous_regime != regime

        regime_record = {
            "timestamp": metrics.timestamp,
            "regime": regime.value,
            "confidence": confidence,
            "previous_regime": previous_regime.value if previous_regime else None,
        }
        self._regime_history.append(regime_record)
        if len(self._regime_history) > 100:
            self._regime_history = self._regime_history[-100:]

        return {
            "current_regime": regime.value,
            "recommended_strategy": recommended,
            "confidence": rec_confidence,
            "reasoning": reasoning,
            "metrics": {
                "avg_funding_rate": round(metrics.avg_funding_rate, 6),
                "positive_funding_pct": round(metrics.positive_funding_pct, 1),
                "volatility_index": round(metrics.volatility_index, 1),
                "trend_strength": round(metrics.trend_strength, 1),
                "range_bound_score": round(metrics.range_bound_score, 1),
                "funding_rate_count": metrics.funding_rate_count,
            },
            "top_funding_symbols": metrics.top_funding_symbols[:3],
            "high_volatility_symbols": metrics.high_volatility_symbols[:3],
            "trending_symbols": metrics.trending_symbols[:3],
            "regime_changed": regime_changed,
            "previous_regime": previous_regime.value if previous_regime else None,
            "timestamp": metrics.timestamp,
        }

    def _determine_regime(self, metrics: MarketMetrics) -> tuple[MarketRegime, int, str]:
        scores = {
            MarketRegime.TRENDING: 0.0,
            MarketRegime.RANGING: 0.0,
            MarketRegime.VOLATILE: 0.0,
            MarketRegime.NEUTRAL: 10.0,
        }
        reasons = []

        if metrics.avg_funding_rate > self.FUNDING_HIGH_THRESHOLD:
            scores[MarketRegime.TRENDING] += 25
            reasons.append(f"High avg funding rate ({metrics.avg_funding_rate:.6f}) favors delta-neutral capture")

        if metrics.positive_funding_pct > 70:
            scores[MarketRegime.TRENDING] += 15
            reasons.append(f"{metrics.positive_funding_pct:.0f}% of pairs have positive funding")

        if metrics.volatility_index > 40:
            scores[MarketRegime.VOLATILE] += 30
            reasons.append(f"Volatility index at {metrics.volatility_index:.0f}/100 signals breakout conditions")
        elif metrics.volatility_index < 20:
            scores[MarketRegime.RANGING] += 20
            reasons.append("Low volatility suggests range-bound conditions")

        if metrics.trend_strength > self.TREND_STRONG_THRESHOLD:
            scores[MarketRegime.TRENDING] += 35
            reasons.append(f"Strong trend detected (strength: {metrics.trend_strength:.0f}/100)")
        elif metrics.trend_strength < 30:
            scores[MarketRegime.RANGING] += 15
            reasons.append("Weak trend signals possible mean-reversion setup")

        if metrics.range_bound_score > 60:
            scores[MarketRegime.RANGING] += 25
            reasons.append(f"Range-bound score {metrics.range_bound_score:.0f}/100 indicates consolidation")

        if len(metrics.high_volatility_symbols) >= 3:
            scores[MarketRegime.VOLATILE] += 20
            reasons.append(f"{len(metrics.high_volatility_symbols)} symbols showing high volatility")

        if len(metrics.trending_symbols) >= 3:
            scores[MarketRegime.TRENDING] += 20
            reasons.append(f"{len(metrics.trending_symbols)} symbols showing strong trends")

        best_regime = max(scores, key=scores.get)
        best_score = scores[best_regime]
        total_possible = sum(scores.values())
        confidence = min(95, int((best_score / max(total_possible, 1)) * 100))

        if confidence < 30:
            best_regime = MarketRegime.NEUTRAL
            confidence = 40
            reasons = ["Market signals are mixed; no clear regime detected"]

        reasoning = ". ".join(reasons) if reasons else "Insufficient data for analysis"

        return best_regime, confidence, reasoning

    def _recommend_strategy_for_regime(self, regime: MarketRegime, metrics: MarketMetrics) -> tuple[str, int]:
        recommendations = {
            MarketRegime.TRENDING: ("momentum_swing", 85),
            MarketRegime.RANGING: ("mean_reversion", 80),
            MarketRegime.VOLATILE: ("volatility_breakout", 85),
            MarketRegime.NEUTRAL: ("delta_neutral", 70),
        }

        strategy, base_conf = recommendations.get(regime, ("delta_neutral", 50))

        if strategy != "delta_neutral" and metrics.avg_funding_rate > self.FUNDING_HIGH_THRESHOLD:
            funding_conf = min(95, base_conf + 10)
            return "delta_neutral", funding_conf

        return strategy, base_conf

    async def get_alerts(self) -> list[dict]:
        alerts = []

        if self._last_regime is None:
            return [{"type": "info", "message": "Market analysis not yet run. Call /api/ai/market-analysis first."}]

        recent = self._regime_history[-5:] if len(self._regime_history) >= 5 else self._regime_history

        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]
            if prev["regime"] != curr["regime"]:
                alerts.append({
                    "type": "regime_change",
                    "severity": "high",
                    "message": f"Market regime changed from {prev['regime']} to {curr['regime']}",
                    "suggestion": self._regime_alert_suggestion(curr["regime"]),
                    "timestamp": curr["timestamp"],
                })

        analysis = await self.analyze_market()

        if analysis["metrics"]["volatility_index"] > 60:
            alerts.append({
                "type": "high_volatility",
                "severity": "medium",
                "message": f"High volatility detected (index: {analysis['metrics']['volatility_index']:.0f})",
                "suggestion": "Consider switching to Volatility Breakout strategy",
                "timestamp": analysis["timestamp"],
            })

        if analysis["metrics"]["avg_funding_rate"] > 0.001:
            alerts.append({
                "type": "high_funding",
                "severity": "medium",
                "message": f"Very high avg funding rate ({analysis['metrics']['avg_funding_rate']:.6f})",
                "suggestion": "Excellent conditions for Delta Neutral funding capture",
                "timestamp": analysis["timestamp"],
            })

        if analysis["metrics"]["trend_strength"] > 75:
            alerts.append({
                "type": "strong_trend",
                "severity": "low",
                "message": f"Strong trend detected (strength: {analysis['metrics']['trend_strength']:.0f})",
                "suggestion": "Momentum Swing strategy may capture extended moves",
                "timestamp": analysis["timestamp"],
            })

        if not alerts:
            alerts.append({
                "type": "info",
                "severity": "low",
                "message": "No significant market alerts. Current conditions are stable.",
                "suggestion": f"Maintain current {self._last_regime.value} regime strategy",
                "timestamp": int(time.time() * 1000),
            })

        return alerts

    def _regime_alert_suggestion(self, new_regime: str) -> str:
        suggestions = {
            "trending": "Consider Momentum Swing to ride the trend",
            "ranging": "Consider Mean Reversion for range-bound profits",
            "volatile": "Consider Volatility Breakout for explosive moves",
            "neutral": "Delta Neutral remains the safest choice in uncertain conditions",
        }
        return suggestions.get(new_regime, "Review your strategy allocation")
