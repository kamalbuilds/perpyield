from __future__ import annotations
import asyncio
import os
import time
import logging
from fastapi import APIRouter, HTTPException, Query

from strategies.basis_arb import BasisArbStrategy

router = APIRouter(tags=["strategy"])
logger = logging.getLogger(__name__)

_strategy_task = None
_rebalancer_task = None


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
    return get_rebalancer()


def _get_vault_manager():
    from main import get_vault_manager
    return get_vault_manager()


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


@router.post("/api/strategy/start")
async def strategy_start():
    global _strategy_task, _rebalancer_task
    if _strategy_task and not _strategy_task.done():
        return {"status": "already_running"}

    vm = _get_vault_manager()
    vm.state.is_active = True
    vm._save_state()

    _strategy_task = asyncio.create_task(_strategy_loop())

    rebalancer = _get_rebalancer()
    interval = int(os.getenv("REBALANCE_INTERVAL", "300"))
    _rebalancer_task = asyncio.create_task(rebalancer.run_loop(interval))

    return {"status": "started", "timestamp": int(time.time() * 1000)}


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
        return _get_strategy().get_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/api/strategy/cycle")
async def run_strategy_cycle():
    try:
        return await _get_vault_manager().run_strategy_cycle()
    except RuntimeError:
        strategy = _get_strategy()
        return {
            "strategy": strategy.get_status(),
            "rebalances": [],
            "pnl": {"vault_value": 0, "net_pnl": 0, "pnl_pct": 0},
            "timestamp": int(time.time() * 1000),
            "note": "No wallet configured. Set PACIFICA_PRIVATE_KEY to enable trading.",
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/positions")
async def get_positions():
    try:
        client = _get_client()
        positions = await client.get_positions()
        strategy = _get_strategy()
        return {
            "live_positions": [p.model_dump() for p in positions],
            "strategy_positions": strategy.get_status(),
        }
    except Exception:
        return {"live_positions": [], "strategy_positions": {}}


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
        rebalancer = _get_rebalancer()
        return await rebalancer.get_delta_summary()
    except Exception:
        return {
            "total_long_exposure": 0,
            "total_short_exposure": 0,
            "net_delta": 0,
            "delta_pct": 0,
            "needs_rebalance": False,
        }


def get_strategy_task():
    return _strategy_task


def get_rebalancer_task():
    return _rebalancer_task
