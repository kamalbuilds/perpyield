import logging
from dataclasses import dataclass, field
from typing import Optional

from strategy.vault_manager import STRATEGY_REGISTRY
from ai_advisor.market_analyzer import MarketAnalyzer, MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class StrategyRecommendation:
    strategy_id: str
    strategy_name: str
    score: float
    confidence: int
    reasoning: str
    risk_level: str
    expected_apy: str
    regime_match: str


@dataclass
class StrategySimulation:
    strategy_id: str
    strategy_name: str
    amount: float
    days: int
    projected_return_pct: float
    projected_return_usd: float
    projected_apy: float
    risk_adjusted_return: float
    confidence: int
    assumptions: list
    best_case: float
    worst_case: float


RISK_PROFILES = {
    "conservative": {
        "max_risk": "Low",
        "preferred_strategies": ["delta_neutral", "mean_reversion"],
        "max_leverage": 2.0,
        "position_size_multiplier": 0.5,
    },
    "moderate": {
        "max_risk": "Medium",
        "preferred_strategies": ["delta_neutral", "momentum_swing", "mean_reversion"],
        "max_leverage": 3.0,
        "position_size_multiplier": 1.0,
    },
    "aggressive": {
        "max_risk": "High",
        "preferred_strategies": ["momentum_swing", "volatility_breakout", "mean_reversion"],
        "max_leverage": 5.0,
        "position_size_multiplier": 1.5,
    },
}

REGIME_STRATEGY_MAP = {
    MarketRegime.TRENDING: {
        "primary": "momentum_swing",
        "secondary": ["delta_neutral", "mean_reversion"],
    },
    MarketRegime.RANGING: {
        "primary": "mean_reversion",
        "secondary": ["delta_neutral", "momentum_swing"],
    },
    MarketRegime.VOLATILE: {
        "primary": "volatility_breakout",
        "secondary": ["delta_neutral", "momentum_swing"],
    },
    MarketRegime.NEUTRAL: {
        "primary": "delta_neutral",
        "secondary": ["mean_reversion", "momentum_swing"],
    },
}

STRATEGY_HISTORICAL_RETURNS = {
    "delta_neutral": {"avg_daily_return": 0.02, "sharpe": 1.8, "max_drawdown": 3.0, "win_rate": 72},
    "momentum_swing": {"avg_daily_return": 0.08, "sharpe": 1.2, "max_drawdown": 15.0, "win_rate": 55},
    "mean_reversion": {"avg_daily_return": 0.04, "sharpe": 1.5, "max_drawdown": 8.0, "win_rate": 62},
    "volatility_breakout": {"avg_daily_return": 0.12, "sharpe": 0.9, "max_drawdown": 25.0, "win_rate": 45},
}


class StrategyRecommender:
    def __init__(self, analyzer: MarketAnalyzer):
        self.analyzer = analyzer

    async def recommend_strategies(self, risk_profile: str = "moderate") -> dict:
        if risk_profile not in RISK_PROFILES:
            risk_profile = "moderate"

        profile = RISK_PROFILES[risk_profile]
        analysis = await self.analyzer.analyze_market()
        regime = MarketRegime(analysis["current_regime"])
        regime_map = REGIME_STRATEGY_MAP.get(regime, REGIME_STRATEGY_MAP[MarketRegime.NEUTRAL])

        recommendations = []

        primary_id = regime_map["primary"]
        primary_score = self._calculate_strategy_score(primary_id, regime, analysis, profile)
        recommendations.append(self._build_recommendation(primary_id, primary_score, regime, analysis, "primary"))

        for sec_id in regime_map["secondary"]:
            if sec_id in profile["preferred_strategies"] or profile["max_risk"] == "High":
                sec_score = self._calculate_strategy_score(sec_id, regime, analysis, profile)
                recommendations.append(self._build_recommendation(sec_id, sec_score, regime, analysis, "secondary"))

        for sid, sdata in STRATEGY_REGISTRY.items():
            if sid not in [r.strategy_id for r in recommendations]:
                if sdata["risk_level"] <= profile["max_risk"]:
                    score = self._calculate_strategy_score(sid, regime, analysis, profile) * 0.5
                    recommendations.append(self._build_recommendation(sid, score, regime, analysis, "fallback"))

        recommendations.sort(key=lambda r: r.score, reverse=True)
        top_3 = recommendations[:3]

        return {
            "risk_profile": risk_profile,
            "current_regime": regime.value,
            "recommendations": [
                {
                    "strategy_id": r.strategy_id,
                    "strategy_name": r.strategy_name,
                    "score": round(r.score, 1),
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "risk_level": r.risk_level,
                    "expected_apy": r.expected_apy,
                    "regime_match": r.regime_match,
                }
                for r in top_3
            ],
            "metrics": analysis["metrics"],
            "timestamp": analysis["timestamp"],
        }

    def _calculate_strategy_score(
        self, strategy_id: str, regime: MarketRegime, analysis: dict, profile: dict
    ) -> float:
        base_score = 50.0
        regime_map = REGIME_STRATEGY_MAP.get(regime, {})

        if strategy_id == regime_map.get("primary"):
            base_score += 30.0
        elif strategy_id in regime_map.get("secondary", []):
            base_score += 15.0

        if strategy_id in profile["preferred_strategies"]:
            base_score += 15.0

        metrics = analysis["metrics"]

        if strategy_id == "delta_neutral":
            if metrics["avg_funding_rate"] > 0.0005:
                base_score += 20.0
            elif metrics["avg_funding_rate"] > 0.0002:
                base_score += 10.0
            if metrics["positive_funding_pct"] > 70:
                base_score += 10.0

        elif strategy_id == "momentum_swing":
            if metrics["trend_strength"] > 60:
                base_score += 20.0
            elif metrics["trend_strength"] > 40:
                base_score += 10.0

        elif strategy_id == "mean_reversion":
            if metrics["range_bound_score"] > 60:
                base_score += 20.0
            elif metrics["range_bound_score"] > 40:
                base_score += 10.0

        elif strategy_id == "volatility_breakout":
            if metrics["volatility_index"] > 40:
                base_score += 20.0
            elif metrics["volatility_index"] > 25:
                base_score += 10.0

        return min(100, base_score)

    def _build_recommendation(
        self, strategy_id: str, score: float, regime: MarketRegime, analysis: dict, match_type: str
    ) -> StrategyRecommendation:
        sdata = STRATEGY_REGISTRY.get(strategy_id, {})
        regime_map = REGIME_STRATEGY_MAP.get(regime, {})
        is_primary = strategy_id == regime_map.get("primary")

        regime_match = "primary" if is_primary else ("secondary" if match_type == "secondary" else "low")

        reasons = []
        if is_primary:
            reasons.append(f"Best match for current {regime.value} market regime")
        elif match_type == "secondary":
            reasons.append(f"Viable alternative in {regime.value} conditions")

        metrics = analysis["metrics"]
        if strategy_id == "delta_neutral" and metrics["avg_funding_rate"] > 0.0005:
            reasons.append("High funding rates create strong delta-neutral opportunity")
        elif strategy_id == "momentum_swing" and metrics["trend_strength"] > 60:
            reasons.append("Strong trend signals favor momentum capture")
        elif strategy_id == "mean_reversion" and metrics["range_bound_score"] > 60:
            reasons.append("Range-bound conditions suit mean reversion approach")
        elif strategy_id == "volatility_breakout" and metrics["volatility_index"] > 40:
            reasons.append("Elevated volatility creates breakout opportunities")

        if not reasons:
            reasons.append("Diversification benefit across market conditions")

        confidence = min(95, int(score * 0.9 + 10))

        return StrategyRecommendation(
            strategy_id=strategy_id,
            strategy_name=sdata.get("name", strategy_id),
            score=score,
            confidence=confidence,
            reasoning=". ".join(reasons),
            risk_level=sdata.get("risk_level", "Unknown"),
            expected_apy=sdata.get("expected_apy", "Unknown"),
            regime_match=regime_match,
        )

    async def simulate_strategy(self, strategy_id: str, amount: float, days: int) -> dict:
        if strategy_id not in STRATEGY_HISTORICAL_RETURNS:
            raise ValueError(f"Unknown strategy: {strategy_id}. Available: {list(STRATEGY_HISTORICAL_RETURNS.keys())}")

        hist = STRATEGY_HISTORICAL_RETURNS[strategy_id]
        sdata = STRATEGY_REGISTRY.get(strategy_id, {})

        avg_daily = hist["avg_daily_return"]
        projected_return_pct = avg_daily * days
        projected_return_usd = amount * (projected_return_pct / 100)
        projected_apy = avg_daily * 365

        risk_adj = projected_apy / (hist["max_drawdown"] + 1)

        confidence = min(90, int(hist["win_rate"] * 0.8 + hist["sharpe"] * 10))

        best_case_pct = projected_return_pct * (1 + hist["sharpe"] * 0.2)
        worst_case_pct = -hist["max_drawdown"] * (days / 30)

        sim = StrategySimulation(
            strategy_id=strategy_id,
            strategy_name=sdata.get("name", strategy_id),
            amount=amount,
            days=days,
            projected_return_pct=round(projected_return_pct, 2),
            projected_return_usd=round(projected_return_usd, 2),
            projected_apy=round(projected_apy, 2),
            risk_adjusted_return=round(risk_adj, 2),
            confidence=confidence,
            assumptions=[
                f"Based on historical avg daily return of {avg_daily:.2f}%",
                f"Assumes Sharpe ratio of {hist['sharpe']:.1f}",
                f"Historical win rate: {hist['win_rate']}%",
                f"Historical max drawdown: {hist['max_drawdown']}%",
                "Past performance does not guarantee future results",
            ],
            best_case=round(amount * (best_case_pct / 100), 2),
            worst_case=round(amount * (worst_case_pct / 100), 2),
        )

        return {
            "simulation": {
                "strategy_id": sim.strategy_id,
                "strategy_name": sim.strategy_name,
                "amount": sim.amount,
                "days": sim.days,
                "projected_return_pct": sim.projected_return_pct,
                "projected_return_usd": sim.projected_return_usd,
                "projected_apy": sim.projected_apy,
                "risk_adjusted_return": sim.risk_adjusted_return,
                "confidence": sim.confidence,
                "best_case": sim.best_case,
                "worst_case": sim.worst_case,
            },
            "assumptions": sim.assumptions,
        }
