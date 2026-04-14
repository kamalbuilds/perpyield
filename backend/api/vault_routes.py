from __future__ import annotations
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from models import DepositRequest, WithdrawRequest
from strategy.vault_manager import list_available_strategies, STRATEGY_REGISTRY

router = APIRouter(tags=["vault"])


def _get_client():
    from main import get_client
    return get_client()


def _get_vault_manager():
    from main import get_vault_manager
    return get_vault_manager()


# ========== Request Models ==========

class CreateVaultRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    creator_address: Optional[str] = None
    strategy_id: str = "delta_neutral"
    strategy_config: Optional[dict] = None


class SwitchStrategyRequest(BaseModel):
    strategy_id: str
    config: Optional[dict] = None


class CloneVaultRequest(BaseModel):
    new_vault_id: str
    cloner_address: str
    custom_name: Optional[str] = None
    custom_description: Optional[str] = None


class PortfolioConfigureRequest(BaseModel):
    allocations: dict[str, float]
    rebalance_threshold: float = 0.05


class WithdrawFeesRequest(BaseModel):
    creator_address: str
    amount: Optional[float] = None


# ========== Vault Management ==========

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
            "strategy": {"id": "delta_neutral", "name": "Delta Neutral"},
        }


@router.post("/api/vault/create")
async def create_vault(req: CreateVaultRequest):
    """Create a new vault with selected strategy."""
    try:
        vm = _get_vault_manager()

        # Validate strategy
        if req.strategy_id not in STRATEGY_REGISTRY:
            raise ValueError(f"Unknown strategy: {req.strategy_id}")

        # Set strategy config before creating
        vm.state.strategy_id = req.strategy_id
        if req.strategy_config:
            vm.state.strategy_config = req.strategy_config

        result = vm.create_vault(
            name=req.name,
            description=req.description,
            creator=req.creator_address
        )

        return {
            **result,
            "strategy_id": req.strategy_id,
            "strategy_name": STRATEGY_REGISTRY[req.strategy_id]["name"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/vault/deposit")
async def vault_deposit(req: DepositRequest):
    try:
        vm = _get_vault_manager()
        if not vm.state.is_active and vm.state.created_at == 0:
            vm.create_vault()
        result = await vm.deposit(req.user_address, req.amount)
        return result
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


# ========== Strategy Switching ==========

@router.post("/api/vault/switch-strategy")
async def switch_strategy(req: SwitchStrategyRequest):
    """Switch vault to a different strategy."""
    try:
        vm = _get_vault_manager()
        result = await vm.switch_strategy(req.strategy_id, req.config)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/vault/strategies")
async def get_vault_strategies():
    """Get all available strategies for this vault."""
    return {
        "current_strategy_id": _get_vault_manager().state.strategy_id,
        "available_strategies": list_available_strategies(),
    }


# ========== Vault Marketplace & Cloning ==========

@router.post("/api/vault/clone")
async def clone_vault(req: CloneVaultRequest):
    """Clone this vault's configuration to create a new vault."""
    try:
        vm = _get_vault_manager()
        template = vm.clone_vault(req.new_vault_id, req.cloner_address)

        # Customize if provided
        if req.custom_name:
            template["template"]["vault_name"] = req.custom_name
        if req.custom_description:
            template["template"]["description"] = req.custom_description

        return template
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/vault/marketplace")
async def vault_marketplace():
    """Get marketplace of cloneable vaults with real performance data from Pacifica."""
    import json
    from pathlib import Path
    from main import get_client

    client = get_client()
    data_dir = Path("data")

    vault_templates = [
        {
            "vault_id": "perpyield-delta-neutral",
            "name": "Delta Neutral Funding Farm",
            "description": "Low-risk funding rate arbitrage. Consistent 5-15% APY.",
            "strategy_id": "delta_neutral",
            "strategy_name": "Delta Neutral (Funding Arbitrage)",
            "risk_level": "Low",
            "expected_apy": "5-20%",
            "creator": "PerpYield Official",
        },
        {
            "vault_id": "perpyield-momentum-master",
            "name": "Momentum Master",
            "description": "Trend-following with EMA+RSI confirmation. Captures major moves.",
            "strategy_id": "momentum_swing",
            "strategy_name": "Momentum Swing",
            "risk_level": "Medium",
            "expected_apy": "15-50%",
            "creator": "PerpYield Official",
        },
        {
            "vault_id": "perpyield-mean-reversion",
            "name": "Mean Reversion Bot",
            "description": "Bollinger Bands bounce strategy. Best in ranging markets.",
            "strategy_id": "mean_reversion",
            "strategy_name": "Mean Reversion",
            "risk_level": "Medium",
            "expected_apy": "10-40%",
            "creator": "PerpYield Official",
        },
        {
            "vault_id": "perpyield-breakout-hunter",
            "name": "Breakout Hunter",
            "description": "Volatility breakout with ATR-based sizing. High reward potential.",
            "strategy_id": "volatility_breakout",
            "strategy_name": "Volatility Breakout",
            "risk_level": "High",
            "expected_apy": "20-80%",
            "creator": "PerpYield Official",
        },
    ]

    for vt in vault_templates:
        state_file = data_dir / f"{vt['vault_id']}.json"
        vt["total_deposited"] = 0
        vt["depositor_count"] = 0
        vt["clone_count"] = 0
        vt["performance_7d"] = None
        vt["performance_30d"] = None

        if state_file.exists():
            try:
                raw = json.loads(state_file.read_text())
                vt["total_deposited"] = raw.get("total_deposited", 0)
                vt["depositor_count"] = len(raw.get("depositors", {}))
                vt["clone_count"] = raw.get("clone_count", 0)

                history = raw.get("performance_history", [])
                now_ms = int(time.time() * 1000)
                week_ms = 7 * 24 * 3600 * 1000
                month_ms = 30 * 24 * 3600 * 1000

                week_points = [h for h in history if h.get("timestamp", 0) >= now_ms - week_ms]
                month_points = [h for h in history if h.get("timestamp", 0) >= now_ms - month_ms]
                deposited = vt["total_deposited"]

                if len(week_points) >= 2:
                    start_val = week_points[0].get("vault_value", 0)
                    end_val = week_points[-1].get("vault_value", 0)
                    ret = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0.0
                    vt["performance_7d"] = f"{ret:.2f}%"
                elif deposited > 0 and history:
                    current = history[-1].get("vault_value", deposited)
                    ret = ((current - deposited) / deposited * 100) if deposited > 0 else 0.0
                    vt["performance_7d"] = f"{ret:.2f}%"

                if len(month_points) >= 2:
                    start_val = month_points[0].get("vault_value", 0)
                    end_val = month_points[-1].get("vault_value", 0)
                    ret = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0.0
                    vt["performance_30d"] = f"{ret:.2f}%"
                elif deposited > 0 and history:
                    current = history[-1].get("vault_value", deposited)
                    ret = ((current - deposited) / deposited * 100) if deposited > 0 else 0.0
                    vt["performance_30d"] = f"{ret:.2f}%"
            except Exception:
                pass

        if vt["performance_7d"] is None and client:
            try:
                from strategy.funding_scanner import FundingScanner
                scanner = FundingScanner(client)
                rates = await scanner.fetch_all_funding_rates()
                if vt["strategy_id"] == "delta_neutral":
                    positive_rates = [r for r in rates if r["funding_rate"] > 0]
                    if positive_rates:
                        avg_funding = sum(r["funding_rate"] for r in positive_rates) / len(positive_rates)
                        est_apy = FundingScanner.rate_to_apy(avg_funding)
                        vt["estimated_apy"] = f"{est_apy:.2f}%"
                elif vt["strategy_id"] == "momentum_swing":
                    sorted_rates = sorted(rates, key=lambda r: abs(float(r.get("volume_24h", 0))), reverse=True)
                    if sorted_rates:
                        top_funding = float(sorted_rates[0].get("funding_rate", 0))
                        est_apy = FundingScanner.rate_to_apy(top_funding)
                        vt["estimated_apy"] = f"{est_apy:.2f}%"
            except Exception:
                pass

        if vt["performance_7d"] is None:
            vt.pop("performance_7d", None)
        if vt["performance_30d"] is None:
            vt.pop("performance_30d", None)

    return {
        "featured_vaults": vault_templates,
        "total_vaults": len(vault_templates),
        "filters": {
            "strategies": list_available_strategies(),
            "risk_levels": ["Low", "Medium", "High"],
        }
    }


@router.get("/api/vault/my-vaults")
async def my_vaults(user_address: str):
    """Get all vaults created by or deposited by this user."""
    try:
        vm = _get_vault_manager()
        user_vaults = []

        # Check if user has deposit in current vault
        if user_address in vm.state.depositors:
            user_vaults.append({
                "vault_id": vm.vault_id,
                "name": vm.state.vault_name or vm.vault_id,
                "my_shares": vm.state.depositors[user_address].shares,
                "my_deposit": vm.state.depositors[user_address].deposited_amount,
                "current_value": vm.state.depositors[user_address].shares * (await vm.get_share_price()),
                "strategy_id": vm.state.strategy_id,
                "strategy_name": STRATEGY_REGISTRY.get(vm.state.strategy_id, {}).get("name", "Unknown"),
                "is_active": vm.state.is_active,
            })

        return {
            "user_address": user_address,
            "vaults": user_vaults,
            "total_vaults": len(user_vaults),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/vault/performance")
async def vault_performance(days: int = 30):
    """Get vault performance history."""
    try:
        vm = _get_vault_manager()

        # Get recent history
        history = vm.state.performance_history[-days:] if days < len(vm.state.performance_history) else vm.state.performance_history

        return {
            "vault_id": vm.vault_id,
            "strategy_id": vm.state.strategy_id,
            "strategy_name": STRATEGY_REGISTRY.get(vm.state.strategy_id, {}).get("name", "Unknown"),
            "performance_history": history,
            "data_points": len(history),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ========== Portfolio Mode ==========

@router.post("/api/vault/portfolio/configure")
async def portfolio_configure(req: PortfolioConfigureRequest):
    """Configure portfolio mode with strategy allocations."""
    try:
        vm = _get_vault_manager()
        result = await vm.configure_portfolio(
            allocations=req.allocations,
            rebalance_threshold=req.rebalance_threshold,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/vault/portfolio/status")
async def portfolio_status():
    """Get portfolio status with per-strategy breakdown and drift."""
    try:
        vm = _get_vault_manager()
        return await vm.get_portfolio_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/vault/portfolio/rebalance")
async def portfolio_rebalance():
    """Rebalance portfolio positions to match target allocations."""
    try:
        vm = _get_vault_manager()
        return await vm.rebalance_portfolio()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ========== Fee System ==========

@router.get("/api/vault/fees")
async def vault_fees():
    """Get current fee structure and accrued fees for this vault."""
    try:
        vm = _get_vault_manager()
        return vm.get_fee_info()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/creator/dashboard")
async def creator_dashboard(creator_address: str):
    """Get creator dashboard with fee earnings, AUM, depositor count."""
    try:
        vm = _get_vault_manager()
        return await vm.get_creator_dashboard(creator_address)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/creator/withdraw-fees")
async def creator_withdraw_fees(req: WithdrawFeesRequest):
    """Withdraw accrued creator fees."""
    try:
        vm = _get_vault_manager()
        return await vm.withdraw_creator_fees(req.creator_address, req.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
