from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

from ai_advisor.market_analyzer import MarketAnalyzer
from ai_advisor.strategy_recommender import StrategyRecommender

router = APIRouter(prefix="/api/ai", tags=["ai-advisor"])
logger = logging.getLogger(__name__)

_analyzer: Optional[MarketAnalyzer] = None
_recommender: Optional[StrategyRecommender] = None


def _get_client():
    from main import get_client
    return get_client()


def _get_analyzer() -> MarketAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = MarketAnalyzer(_get_client())
    return _analyzer


def _get_recommender() -> StrategyRecommender:
    global _recommender
    if _recommender is None:
        _recommender = StrategyRecommender(_get_analyzer())
    return _recommender


class RecommendRequest(BaseModel):
    risk_profile: Literal["conservative", "moderate", "aggressive"] = "moderate"


class SimulateRequest(BaseModel):
    strategy_id: str
    amount: float = 1000.0
    days: int = 30


@router.get("/market-analysis")
async def market_analysis():
    try:
        analyzer = _get_analyzer()
        result = await analyzer.analyze_market()
        return {"success": True, "data": result}
    except Exception as exc:
        logger.error(f"Market analysis failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/recommend-strategy")
async def recommend_strategy(req: RecommendRequest):
    try:
        recommender = _get_recommender()
        result = await recommender.recommend_strategies(req.risk_profile)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.error(f"Strategy recommendation failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/simulate")
async def simulate_strategy(req: SimulateRequest):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if req.days < 1 or req.days > 365:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 365")

    try:
        recommender = _get_recommender()
        result = await recommender.simulate_strategy(req.strategy_id, req.amount, req.days)
        return {"success": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Simulation failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/alerts")
async def get_alerts():
    try:
        analyzer = _get_analyzer()
        alerts = await analyzer.get_alerts()
        return {"success": True, "data": alerts}
    except Exception as exc:
        logger.error(f"Alerts fetch failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))
