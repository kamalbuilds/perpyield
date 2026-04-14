from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/orders", tags=["orders"])


def _get_client():
    from main import get_client
    return get_client()


class MarketOrderRequest(BaseModel):
    symbol: str
    side: str
    amount: str
    reduce_only: bool = False
    slippage_percent: str = "0.5"


class LimitOrderRequest(BaseModel):
    symbol: str
    side: str
    price: str
    amount: str
    reduce_only: bool = False
    tif: str = "GTC"


class CancelOrderRequest(BaseModel):
    symbol: str
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None


class CancelAllRequest(BaseModel):
    symbol: Optional[str] = None


class TPSLRequest(BaseModel):
    symbol: str
    side: str
    take_profit: Optional[dict] = None
    stop_loss: Optional[dict] = None


class LeverageRequest(BaseModel):
    symbol: str
    leverage: int


@router.post("/market")
async def create_market_order(req: MarketOrderRequest):
    try:
        result = await _get_client().create_market_order(
            symbol=req.symbol.upper(),
            side=req.side,
            amount=req.amount,
            reduce_only=req.reduce_only,
            slippage_percent=req.slippage_percent,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/limit")
async def create_limit_order(req: LimitOrderRequest):
    try:
        result = await _get_client().create_limit_order(
            symbol=req.symbol.upper(),
            side=req.side,
            price=req.price,
            amount=req.amount,
            reduce_only=req.reduce_only,
            tif=req.tif,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/cancel")
async def cancel_order(req: CancelOrderRequest):
    try:
        result = await _get_client().cancel_order(
            req.symbol.upper(), req.order_id, req.client_order_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/cancel-all")
async def cancel_all_orders(req: CancelAllRequest):
    try:
        result = await _get_client().cancel_all_orders(
            req.symbol.upper() if req.symbol else None
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/tpsl")
async def set_tpsl(req: TPSLRequest):
    try:
        result = await _get_client().set_tpsl(
            symbol=req.symbol.upper(),
            side=req.side,
            take_profit=req.take_profit,
            stop_loss=req.stop_loss,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/leverage")
async def update_leverage(req: LeverageRequest):
    try:
        result = await _get_client().update_leverage(req.symbol.upper(), req.leverage)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
