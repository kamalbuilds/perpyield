from __future__ import annotations
import time
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/market", tags=["market"])


def _get_client():
    from main import get_client
    return get_client()


def _get_scanner():
    from main import get_scanner
    return get_scanner()


@router.get("/info")
async def market_info():
    try:
        markets = await _get_client().get_markets()
        return {"success": True, "data": [m.model_dump() for m in markets]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/prices")
async def prices():
    try:
        data = await _get_client().get_prices()
        return {"success": True, "data": [p.model_dump() for p in data]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/price/{symbol}")
async def price_for_symbol(symbol: str):
    try:
        p = await _get_client().get_price(symbol.upper())
        if not p:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        return {"success": True, "data": p.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/funding-rates")
async def funding_rates():
    try:
        rates = await _get_client().get_funding_rates()
        return {"success": True, "data": rates}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orderbook/{symbol}")
async def orderbook(symbol: str, agg_level: int = Query(1)):
    try:
        book = await _get_client().get_orderbook(symbol.upper(), agg_level)
        return {"success": True, "data": book.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/candles/{symbol}")
async def candles(
    symbol: str,
    interval: str = Query("1h"),
    days: int = Query(default=7, ge=1, le=365),
):
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000
    try:
        data = await _get_client().get_candles(symbol.upper(), interval, start_ms, end_ms)
        return {"success": True, "data": [c.model_dump() for c in data]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
