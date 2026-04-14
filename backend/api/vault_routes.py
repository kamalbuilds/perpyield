from __future__ import annotations
from fastapi import APIRouter, HTTPException
from models import DepositRequest, WithdrawRequest

router = APIRouter(tags=["vault"])


def _get_client():
    from main import get_client
    return get_client()


def _get_vault_manager():
    from main import get_vault_manager
    return get_vault_manager()


@router.get("/api/vault/status")
async def vault_status():
    try:
        vm = _get_vault_manager()
        return await vm.get_vault_info()
    except Exception:
        return {
            "vault_id": "default",
            "is_active": False,
            "created_at": 0,
            "total_deposited": 0,
            "vault_value": 0,
            "share_price": 1.0,
            "total_shares": 0,
            "net_pnl": 0,
            "pnl_pct": 0,
            "annualized_return": 0,
            "depositor_count": 0,
            "active_positions": 0,
        }


@router.post("/api/vault/deposit")
async def vault_deposit(req: DepositRequest):
    try:
        vm = _get_vault_manager()
        if not vm.state.is_active and vm.state.created_at == 0:
            vm.create_vault()
        return await vm.deposit(req.user_address, req.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/vault/withdraw")
async def vault_withdraw(req: WithdrawRequest):
    try:
        vm = _get_vault_manager()
        dep = vm.state.depositors.get(req.user_address)
        if not dep:
            raise ValueError(f"No deposits found for {req.user_address}")
        if req.shares > dep.shares:
            raise ValueError(f"Insufficient shares: have {dep.shares}, requested {req.shares}")
        share_price = 1.0
        if vm.state.total_shares > 0 and _get_client().public_key:
            share_price = await vm.get_share_price()
        withdrawal_amount = req.shares * share_price
        dep.shares -= req.shares
        vm.state.total_shares -= req.shares
        if dep.shares <= 0.000001:
            del vm.state.depositors[req.user_address]
        vm._save_state()
        return {
            "depositor": req.user_address,
            "shares_redeemed": req.shares,
            "amount_received": withdrawal_amount,
            "share_price": share_price,
            "remaining_shares": dep.shares if req.user_address in vm.state.depositors else 0,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/vault/pnl")
async def vault_pnl():
    try:
        return await _get_vault_manager().calculate_pnl()
    except RuntimeError:
        vm = _get_vault_manager()
        return {
            "vault_value": vm.state.total_deposited,
            "total_deposited": vm.state.total_deposited,
            "net_pnl": 0,
            "pnl_pct": 0,
            "funding_earned": vm.state.total_funding_earned,
            "fees_paid": vm.state.total_fees_paid,
            "annualized_return": 0,
            "share_price": 1.0,
            "total_shares": vm.state.total_shares,
            "depositor_count": len(vm.state.depositors),
            "age_hours": 0,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
