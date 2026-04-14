from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["backtest"])


def _get_client():
    from main import get_client
    return get_client()


def _get_backtester():
    from main import get_backtester
    return get_backtester()


@router.get("/api/backtest/multi")
async def backtest_multi(
    symbols: str = Query(default="BTC,ETH,SOL"),
    days: int = Query(default=30, ge=1, le=365),
):
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=400, detail="Provide at least one symbol")
    try:
        from backtester import Backtester as SimpleBacktester
        return await SimpleBacktester(_get_client()).backtest_multi_symbol(sym_list, days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/api/backtest/{symbol}")
async def backtest_symbol(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365),
    initial_capital: float = Query(default=10000.0, ge=100),
):
    try:
        bt = _get_backtester()
        result = await bt.simulate(symbol, days)
        curve = result.equity_curve
        if len(curve) > 100:
            step = max(1, len(curve) // 100)
            curve = curve[::step]
            if curve[-1] != result.equity_curve[-1]:
                curve.append(result.equity_curve[-1])
        return {
            "strategy": "delta_neutral",
            "pair": result.symbol,
            "start_date": result.period_start,
            "end_date": result.period_end,
            "total_return_pct": round(result.total_return_pct, 4),
            "annualized_apy": round(result.annualized_return_pct, 4),
            "sharpe_ratio": round(result.sharpe_ratio, 4),
            "max_drawdown_pct": round(result.max_drawdown_pct, 4),
            "win_rate": round(result.win_rate, 2),
            "total_trades": result.total_trades,
            "funding_earned": round(result.total_funding_collected, 4),
            "trading_fees": round(result.total_fees_paid, 4),
            "net_pnl": round(result.final_capital - result.initial_capital, 4),
            "equity_curve": curve,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
