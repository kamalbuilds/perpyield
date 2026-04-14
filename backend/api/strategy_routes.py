from __future__ import annotations
import asyncio
import os
import time
import logging
from dataclasses import fields as dataclass_fields
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from strategies.basis_arb import BasisArbStrategy
from strategy import (
    MomentumSwingStrategy,
    MeanReversionStrategy,
    VolatilityBreakoutStrategy,
    MomentumConfig,
    MeanReversionConfig,
    VolatilityBreakoutConfig,
)
from strategy.vault_manager import STRATEGY_REGISTRY, list_available_strategies, get_strategy_class

router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)

_strategy_task = None
_rebalancer_task = None

# Strategy instance cache for backtesting
_strategy_instances: dict[str, any] = {}


class StrategySwitchRequest(BaseModel):
    strategy_id: str
    config: Optional[dict] = None


class AddMarginRequest(BaseModel):
    symbol: str
    side: str
    amount: str
    isolated: bool = False


class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    days: int = 30
    initial_capital: float = 10_000.0
    config: Optional[dict] = None


class TPSLRequest(BaseModel):
    symbol: str
    side: str
    take_profit: Optional[dict] = None
    stop_loss: Optional[dict] = None
    tp_price: Optional[str] = None
    sl_price: Optional[str] = None


def _get_client():
    from main import get_client
    return get_client()


def _get_scanner():
    from main import get_scanner
    return get_scanner()


def _get_strategy():
    from main import get_strategy
    return get_strategy()


def _get_rebalancer():
    from main import get_rebalancer
    return _get_rebalancer()


def _get_vault_manager():
    from main import get_vault_manager
    return get_vault_manager()


def _filter_config(config_class, config: dict) -> dict:
    """Filter config dict to only include keys accepted by the dataclass."""
    valid_keys = {f.name for f in dataclass_fields(config_class)}
    return {k: v for k, v in config.items() if k in valid_keys}


def _get_strategy_instance(strategy_id: str, config: Optional[dict] = None):
    """Get or create a strategy instance for backtesting."""
    cache_key = f"{strategy_id}_{hash(str(config))}"

    if cache_key not in _strategy_instances:
        client = _get_client()
        strategy_class, config_class = get_strategy_class(strategy_id)

        if strategy_class is None:
            raise ValueError(f"Unknown strategy: {strategy_id}")

        filtered = _filter_config(config_class, config) if config else {}
        cfg = config_class(**filtered) if filtered else config_class()
        _strategy_instances[cache_key] = strategy_class(client, cfg)

    return _strategy_instances[cache_key]


async def _strategy_loop():
    interval = int(os.getenv("REBALANCE_INTERVAL", "300"))
    logger.info(f"Strategy loop started, interval={interval}s")
    while True:
        try:
            vm = _get_vault_manager()
            result = await vm.run_strategy_cycle()
            logger.info(f"Strategy cycle complete: {result.get('strategy', {})}")
        except Exception as e:
            logger.error(f"Strategy loop error: {e}")
        await asyncio.sleep(interval)


# ========== Strategy Marketplace ==========

@router.get("/api/strategies/marketplace")
async def get_strategy_marketplace():
    """Get all available strategies for the marketplace."""
    return {
        "strategies": list_available_strategies(),
        "total_count": len(STRATEGY_REGISTRY),
    }


@router.get("/api/strategies/{strategy_id}/info")
async def get_strategy_info(strategy_id: str):
    """Get detailed info about a specific strategy."""
    if strategy_id not in STRATEGY_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    info = STRATEGY_REGISTRY[strategy_id]
    config_class = info.get("config_class")
    config_defaults = {}
    if config_class:
        config_defaults = {
            f.name: getattr(config_class(), f.name)
            for f in dataclass_fields(config_class)
        }
    return {
        "id": strategy_id,
        "name": info["name"],
        "description": info["description"],
        "indicators": info["indicators"],
        "risk_level": info["risk_level"],
        "expected_apy": info["expected_apy"],
        "config_defaults": config_defaults,
    }


@router.post("/api/strategies/{strategy_id}/backtest")
async def backtest_strategy(req: BacktestRequest):
    """Run a backtest for a specific strategy."""
    try:
        from strategy.backtester import Backtester, BacktestConfig

        client = _get_client()

        bt_config = BacktestConfig(initial_capital=req.initial_capital)

        if req.config:
            strategy_class, config_class = get_strategy_class(req.strategy_id)
            if config_class:
                filtered = _filter_config(config_class, req.config)
                strategy_cfg = config_class(**filtered)

                if req.strategy_id == "delta_neutral" and hasattr(strategy_cfg, "min_funding_rate"):
                    bt_config.min_funding_rate = strategy_cfg.min_funding_rate
                if hasattr(strategy_cfg, "max_positions"):
                    bt_config.max_positions = strategy_cfg.max_positions
                if hasattr(strategy_cfg, "max_leverage"):
                    bt_config.leverage = strategy_cfg.max_leverage

        bt = Backtester(client, bt_config)

        result = await bt.simulate(req.symbol, req.days)

        return {
            "strategy_id": req.strategy_id,
            "symbol": req.symbol,
            "days": req.days,
            "backtest": {
                "total_return_pct": round(result.total_return_pct, 4),
                "annualized_apy": round(result.annualized_return_pct, 4),
                "sharpe_ratio": round(result.sharpe_ratio, 4),
                "max_drawdown_pct": round(result.max_drawdown_pct, 4),
                "win_rate": round(result.win_rate, 2),
                "total_trades": result.total_trades,
                "funding_earned": round(result.total_funding_collected, 4),
                "trading_fees": round(result.total_fees_paid, 4),
                "net_pnl": round(result.final_capital - result.initial_capital, 4),
            },
            "equity_curve_sample": result.equity_curve[::max(1, len(result.equity_curve)//50)][:50],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Backtest error for {req.strategy_id}/{req.symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


# ========== Strategy Control ==========

@router.post("/api/strategy/start")
async def strategy_start():
    global _strategy_task, _rebalancer_task
    if _strategy_task and not _strategy_task.done():
        return {"status": "already_running"}

    vm = _get_vault_manager()
    vm.state.is_active = True
    vm._save_state()

    _strategy_task = asyncio.create_task(_strategy_loop())

    # Only run rebalancer for delta_neutral
    if vm.state.strategy_id == "delta_neutral":
        rebalancer = _get_rebalancer()
        interval = int(os.getenv("REBALANCE_INTERVAL", "300"))
        _rebalancer_task = asyncio.create_task(rebalancer.run_loop(interval))

    return {
        "status": "started",
        "timestamp": int(time.time() * 1000),
        "strategy_id": vm.state.strategy_id,
        "strategy_name": STRATEGY_REGISTRY.get(vm.state.strategy_id, {}).get("name", "Unknown"),
    }


@router.post("/api/strategy/stop")
async def strategy_stop():
    global _strategy_task, _rebalancer_task

    if _strategy_task and not _strategy_task.done():
        _strategy_task.cancel()
        try:
            await _strategy_task
        except asyncio.CancelledError:
            pass
        _strategy_task = None

    if _rebalancer_task and not _rebalancer_task.done():
        _get_rebalancer().stop_loop()
        _rebalancer_task.cancel()
        try:
            await _rebalancer_task
        except asyncio.CancelledError:
            pass
        _rebalancer_task = None

    vm = _get_vault_manager()
    vm.state.is_active = False
    vm._save_state()

    return {"status": "stopped", "timestamp": int(time.time() * 1000)}


@router.get("/api/strategy/status")
async def strategy_status():
    try:
        vm = _get_vault_manager()
        return {
            "vault_strategy": vm.strategy.get_status(),
            "current_strategy_id": vm.state.strategy_id,
            "strategy_name": STRATEGY_REGISTRY.get(vm.state.strategy_id, {}).get("name", "Unknown"),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/strategy/cycle")
async def run_strategy_cycle():
    try:
        return await _get_vault_manager().run_strategy_cycle()
    except RuntimeError:
        vm = _get_vault_manager()
        return {
            "strategy": vm.strategy.get_status(),
            "strategy_id": vm.state.strategy_id,
            "rebalances": [],
            "pnl": {"vault_value": 0, "net_pnl": 0, "pnl_pct": 0},
            "timestamp": int(time.time() * 1000),
            "note": "No wallet configured. Set PACIFICA_PRIVATE_KEY to enable trading.",
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ========== Strategy Scanning ==========

@router.post("/api/positions/tpsl")
async def set_tpsl(req: TPSLRequest):
    """Set take profit / stop loss for a position via PacificaClient.set_tpsl()."""
    client = _get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pacifica client not configured. Set PACIFICA_PRIVATE_KEY in .env")
    try:
        result = await client.set_tpsl(
            symbol=req.symbol.upper(),
            side=req.side,
            take_profit=req.take_profit,
            stop_loss=req.stop_loss,
            tp_price=req.tp_price,
            sl_price=req.sl_price,
        )
        return result
    except Exception as exc:
        logger.error(f"TP/SL set failed for {req.symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/positions/margin")
async def add_margin(req: AddMarginRequest):
    """Add margin to an existing position via Pacifica API."""
    client = _get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pacifica client not configured. Set PACIFICA_PRIVATE_KEY in .env")
    try:
        pacifica_side = "bid" if req.side.lower() == "long" else "ask" if req.side.lower() == "short" else req.side
        result = await client.add_margin(
            symbol=req.symbol.upper(),
            side=pacifica_side,
            amount=req.amount,
            isolated=req.isolated,
        )
        logger.info(f"Margin added: {req.symbol} {req.side} +{req.amount}")
        return {
            "status": "ok",
            "symbol": req.symbol.upper(),
            "side": req.side,
            "amount_added": req.amount,
            "pacific_response": result,
        }
    except Exception as exc:
        logger.error(f"Add margin failed for {req.symbol}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/positions")
async def get_positions():
    """Get live positions from Pacifica and strategy positions."""
    try:
        client = _get_client()
        raw_positions = await client.get_positions()
        vm = _get_vault_manager()
        
        # Map Pacifica positions to frontend format
        live_positions = []
        for p in raw_positions:
            # Convert "bid" -> "long", "ask" -> "short"
            side = "long" if p.side == "bid" else "short" if p.side == "ask" else p.side
            live_positions.append({
                "symbol": p.symbol,
                "side": side,
                "size": float(p.amount),
                "entry_price": float(p.entry_price),
                "entry_funding_rate": 0.0,
                "cumulative_funding": float(p.funding),
                "held_since": p.created_at,
                "mark_price": None,  # Will be filled by frontend from WS
            })
        
        return {
            "live_positions": live_positions,
            "strategy_positions": vm.strategy.get_status(),
            "current_strategy_id": vm.state.strategy_id,
        }
    except Exception:
        return {"live_positions": [], "strategy_positions": {}, "current_strategy_id": "unknown"}


@router.get("/api/strategies/funding")
async def funding_opportunities(min_yield: float = Query(default=5.0)):
    try:
        scanner = _get_scanner()
        scanner.min_apy = min_yield
        opps = await scanner.scan(fetch_history=True, max_history_fetches=10)
        return [
            {
                "symbol": o.symbol,
                "funding_rate": o.funding_rate,
                "next_funding_rate": o.next_funding_rate,
                "apy_current": round(o.apy_current, 4),
                "apy_next": round(o.apy_next, 4),
                "mark_price": o.mark_price,
                "oracle_price": o.oracle_price,
                "open_interest": o.open_interest,
                "volume_24h": o.volume_24h,
                "max_leverage": o.max_leverage,
                "trend": o.trend,
            }
            for o in opps
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/strategies/basis")
async def basis_opportunities():
    try:
        return await BasisArbStrategy.scan_basis_opportunities(_get_client())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/scanner/summary")
async def scanner_summary():
    try:
        scanner = _get_scanner()
        return await scanner.summary()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/delta/summary")
async def delta_summary():
    try:
        vm = _get_vault_manager()
        # Only show delta for delta_neutral strategy
        if vm.state.strategy_id == "delta_neutral":
            rebalancer = _get_rebalancer()
            return await rebalancer.get_delta_summary()
        else:
            return {
                "strategy_id": vm.state.strategy_id,
                "delta_tracking": "not_applicable",
                "note": "Delta tracking only available for delta_neutral strategy",
            }
    except Exception:
        return {
            "total_long_exposure": 0,
            "total_short_exposure": 0,
            "net_delta": 0,
            "delta_pct": 0,
            "needs_rebalance": False,
        }


@router.get("/api/strategies/momentum-scan")
async def momentum_scan():
    """Scan for momentum swing opportunities."""
    try:
        strategy = MomentumSwingStrategy(_get_client())
        signals = await strategy.scan_opportunities()
        return [
            {
                "symbol": s.symbol,
                "direction": s.direction.value,
                "strength": round(s.strength, 2),
                "entry_price": s.entry_price,
                "stop_loss": s.stop_loss,
                "take_profit": s.take_profit,
                "indicators": s.indicators,
            }
            for s in signals[:5]
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/strategies/reversion-scan")
async def reversion_scan():
    """Scan for mean reversion opportunities."""
    try:
        strategy = MeanReversionStrategy(_get_client())
        signals = await strategy.scan_opportunities()
        return [
            {
                "symbol": s.symbol,
                "state": s.state.value,
                "deviation_score": round(s.deviation_score, 2),
                "entry_price": s.entry_price,
                "target_price": s.target_price,
                "indicators": s.indicators,
            }
            for s in signals[:5]
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/strategies/breakout-scan")
async def breakout_scan():
    """Scan for volatility breakout opportunities."""
    try:
        strategy = VolatilityBreakoutStrategy(_get_client())
        signals = await strategy.scan_opportunities()
        return [
            {
                "symbol": s.symbol,
                "direction": s.direction.value,
                "volatility_score": round(s.volatility_score, 2),
                "entry_price": s.entry_price,
                "atr": s.atr,
                "indicators": s.indicators,
            }
            for s in signals[:5]
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def get_strategy_task():
    return _strategy_task


def get_rebalancer_task():
    return _rebalancer_task
