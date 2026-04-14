from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["risk"])


def _get_vault_manager():
    from main import get_vault_manager
    return get_vault_manager()


class RiskConfigureRequest(BaseModel):
    daily_loss_limit_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    consecutive_losses_limit: Optional[int] = None
    max_position_size_pct: Optional[float] = None
    max_correlated_exposure: Optional[float] = None
    max_sector_exposure: Optional[float] = None
    enable_circuit_breaker: Optional[bool] = None
    funding_rate_flip_protection: Optional[bool] = None
    fixed_risk_per_trade_pct: Optional[float] = None
    position_sizing_method: Optional[str] = None
    kelly_fraction: Optional[float] = None
    volatility_adjust: Optional[bool] = None


class EmergencyStopRequest(BaseModel):
    stop_type: str = "kill_switch"


@router.get("/api/vault/risk/status")
async def risk_status():
    try:
        vm = _get_vault_manager()
        return await vm.get_risk_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/vault/risk/configure")
async def configure_risk(req: RiskConfigureRequest):
    try:
        vm = _get_vault_manager()
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(status_code=400, detail="No configuration updates provided")
        return vm.configure_risk(updates)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/vault/emergency-stop")
async def emergency_stop(req: EmergencyStopRequest):
    try:
        vm = _get_vault_manager()
        if req.stop_type not in ("kill_switch", "gradual_unwind"):
            raise HTTPException(status_code=400, detail="stop_type must be 'kill_switch' or 'gradual_unwind'")
        result = await vm.emergency_stop(req.stop_type)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/vault/resume-trading")
async def resume_trading():
    try:
        vm = _get_vault_manager()
        return await vm.resume_trading()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
