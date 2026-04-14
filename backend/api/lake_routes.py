from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/lake", tags=["lake"])


def _get_client():
    from main import get_client
    return get_client()


class CreateLakeRequest(BaseModel):
    nickname: Optional[str] = None


class LakeTransferRequest(BaseModel):
    lake_address: str
    amount: str


@router.post("/create")
async def create_lake(req: CreateLakeRequest):
    try:
        result = await _get_client().create_lake(req.nickname)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/deposit")
async def lake_deposit(req: LakeTransferRequest):
    try:
        result = await _get_client().lake_deposit(req.lake_address, req.amount)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/withdraw")
async def lake_withdraw(req: LakeTransferRequest):
    try:
        result = await _get_client().lake_withdraw(req.lake_address, req.amount)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
