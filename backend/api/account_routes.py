from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/account", tags=["account"])


def _get_client():
    from main import get_client
    return get_client()


@router.get("/info")
async def account_info(address: str | None = Query(None)):
    try:
        info = await _get_client().get_account(address)
        return {"success": True, "data": info.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/positions")
async def positions(address: str | None = Query(None)):
    try:
        pos = await _get_client().get_positions(address)
        return {"success": True, "data": [p.model_dump() for p in pos]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orders")
async def open_orders(address: str | None = Query(None)):
    try:
        orders = await _get_client().get_open_orders(address)
        return {"success": True, "data": [o.model_dump() for o in orders]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/funding-history")
async def funding_history(
    address: str | None = Query(None),
    limit: int = Query(50),
    cursor: str | None = Query(None),
):
    try:
        result = await _get_client().get_funding_history(address, limit, cursor)
        return {
            "success": True,
            "data": [r.model_dump() for r in result["records"]],
            "next_cursor": result["next_cursor"],
            "has_more": result["has_more"],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/balance-history")
async def balance_history(
    address: str | None = Query(None),
    limit: int = Query(50),
    cursor: str | None = Query(None),
):
    try:
        result = await _get_client().get_balance_history(address, limit, cursor)
        return {
            "success": True,
            "data": [r.model_dump() for r in result["records"]],
            "next_cursor": result["next_cursor"],
            "has_more": result["has_more"],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/trade-history")
async def trade_history(
    address: str | None = Query(None),
    limit: int = Query(50),
    cursor: str | None = Query(None),
):
    try:
        result = await _get_client().get_trade_history(address, limit, cursor)
        return {
            "success": True,
            "data": [r.model_dump() for r in result["records"]],
            "next_cursor": result["next_cursor"],
            "has_more": result["has_more"],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
