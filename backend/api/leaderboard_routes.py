from __future__ import annotations

import json
import time
import math
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter(tags=["leaderboard"])
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def _compute_sharpe(history: list[dict]) -> float:
    if len(history) < 2:
        return 0.0
    returns = []
    for i in range(1, len(history)):
        prev = history[i - 1].get("vault_value", 0)
        curr = history[i].get("vault_value", 0)
        if prev > 0:
            returns.append((curr - prev) / prev)
    if not returns:
        return 0.0
    avg = sum(returns) / len(returns)
    variance = sum((r - avg) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance) if variance > 0 else 0.0001
    return (avg / std) * math.sqrt(365) if std > 0 else 0.0


def _load_all_vaults() -> list[dict]:
    vaults = []
    if not DATA_DIR.exists():
        return vaults
    for f in DATA_DIR.glob("*.json"):
        if f.name == "risk_state.json" or f.name.endswith("_social.json"):
            continue
        try:
            raw = json.loads(f.read_text())
            vaults.append(raw)
        except Exception:
            continue
    return vaults


async def _enrich_featured_vaults() -> list[dict]:
    from strategy.vault_manager import STRATEGY_REGISTRY
    from main import get_client

    client = get_client()

    featured = [
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

    on_disk = {v.get("vault_id", "unknown"): v for v in _load_all_vaults() if v.get("vault_id")}

    for fv in featured:
        disk = on_disk.get(fv["vault_id"])
        if disk:
            fv["total_deposited"] = disk.get("total_deposited", 0)
            fv["clone_count"] = disk.get("clone_count", 0)
            fv["depositor_count"] = len(disk.get("depositors", {}))
            history = disk.get("performance_history", [])
            fv["performance_history"] = history
        else:
            fv["total_deposited"] = 0
            fv["clone_count"] = 0
            fv["depositor_count"] = 0
            fv["performance_history"] = []

    now_ms = int(time.time() * 1000)
    week_ms = 7 * 24 * 3600 * 1000
    month_ms = 30 * 24 * 3600 * 1000

    for fv in featured:
        history = fv.get("performance_history", [])

        if client and fv.get("total_deposited", 0) > 0:
            try:
                from strategy.vault_manager import VaultManager
                vm = VaultManager(client, vault_id=fv["vault_id"])
                vault_value = await vm.get_total_vault_value()
                if history:
                    last_recorded = history[-1].get("vault_value", 0)
                    if vault_value != last_recorded:
                        history.append({
                            "timestamp": now_ms,
                            "vault_value": vault_value,
                            "net_pnl": vault_value - fv["total_deposited"],
                            "pnl_pct": ((vault_value - fv["total_deposited"]) / fv["total_deposited"] * 100) if fv["total_deposited"] > 0 else 0.0,
                        })
            except Exception as e:
                logger.warning(f"Could not fetch live vault value for {fv['vault_id']}: {e}")

        if not history:
            if client:
                try:
                    from strategy.funding_scanner import FundingScanner
                    scanner = FundingScanner(client)
                    rates = await scanner.fetch_all_funding_rates()
                    strategy_id = fv["strategy_id"]
                    if strategy_id == "delta_neutral":
                        positive_rates = [r for r in rates if r["funding_rate"] > 0]
                        if positive_rates:
                            avg_funding = sum(r["funding_rate"] for r in positive_rates) / len(positive_rates)
                            fv["estimated_apy"] = round(FundingScanner.rate_to_apy(avg_funding), 2)
                except Exception:
                    pass
            fv["return_7d"] = 0.0
            fv["return_30d"] = 0.0
            fv["return_all"] = 0.0
            fv["sharpe_ratio"] = 0.0
            continue

        week_points = [h for h in history if h.get("timestamp", 0) >= now_ms - week_ms]
        month_points = [h for h in history if h.get("timestamp", 0) >= now_ms - month_ms]

        if len(week_points) >= 2:
            start_val = week_points[0].get("vault_value", 0)
            end_val = week_points[-1].get("vault_value", 0)
            fv["return_7d"] = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0.0
        else:
            deposited = fv.get("total_deposited", 0)
            current = history[-1].get("vault_value", deposited)
            fv["return_7d"] = ((current - deposited) / deposited * 100) if deposited > 0 else 0.0

        if len(month_points) >= 2:
            start_val = month_points[0].get("vault_value", 0)
            end_val = month_points[-1].get("vault_value", 0)
            fv["return_30d"] = ((end_val - start_val) / start_val * 100) if start_val > 0 else 0.0
        else:
            deposited = fv.get("total_deposited", 0)
            current = history[-1].get("vault_value", deposited)
            fv["return_30d"] = ((current - deposited) / deposited * 100) if deposited > 0 else 0.0

        deposited = fv.get("total_deposited", 0)
        first_val = history[0].get("vault_value", deposited)
        last_val = history[-1].get("vault_value", deposited)
        fv["return_all"] = ((last_val - first_val) / first_val * 100) if first_val > 0 else 0.0

        fv["sharpe_ratio"] = _compute_sharpe(history)

        social_path = DATA_DIR / f"{fv['vault_id']}_social.json"
        if social_path.exists():
            try:
                social = json.loads(social_path.read_text())
                fv["clone_count"] = social.get("clone_count", fv.get("clone_count", 0))
                fv["follower_count"] = social.get("follower_count", 0)
                fv["view_count"] = social.get("view_count", 0)
                fv["weekly_depositors"] = social.get("weekly_depositors", 0)
            except Exception:
                fv["follower_count"] = 0
                fv["view_count"] = 0
                fv["weekly_depositors"] = 0
        else:
            fv["follower_count"] = 0
            fv["view_count"] = 0
            fv["weekly_depositors"] = 0

    return featured


@router.get("/api/leaderboard/vaults")
async def vault_leaderboard(
    period: str = Query(default="7d", pattern="^(7d|30d|all)$"),
    sort_by: str = Query(default="return", pattern="^(return|sharpe|tvl|clones)$"),
):
    vaults = await _enrich_featured_vaults()

    period_return_key = {"7d": "return_7d", "30d": "return_30d", "all": "return_all"}.get(period, "return_7d")
    sort_key_map = {
        "return": period_return_key,
        "sharpe": "sharpe_ratio",
        "tvl": "total_deposited",
        "clones": "clone_count",
    }
    sort_key = sort_key_map.get(sort_by, "return_7d")

    vaults.sort(key=lambda v: v.get(sort_key, 0), reverse=True)

    ranked = []
    for idx, v in enumerate(vaults):
        return_val = v.get(period_return_key, 0)
        entry = {
            "rank": idx + 1,
            "vault_id": v["vault_id"],
            "name": v["name"],
            "creator": v.get("creator", "Unknown"),
            "strategy_id": v["strategy_id"],
            "strategy_name": v["strategy_name"],
            "risk_level": v["risk_level"],
            "tvl": v.get("total_deposited", 0),
            "return_7d": round(v.get("return_7d", 0), 2),
            "return_30d": round(v.get("return_30d", 0), 2),
            "return_all": round(v.get("return_all", 0), 2),
            "sharpe_ratio": round(v.get("sharpe_ratio", 0), 2),
            "clone_count": v.get("clone_count", 0),
            "follower_count": v.get("follower_count", 0),
            "weekly_depositors": v.get("weekly_depositors", 0),
        }
        if v.get("estimated_apy") is not None:
            entry["estimated_apy"] = v["estimated_apy"]
        ranked.append(entry)

    return {
        "period": period,
        "sort_by": sort_by,
        "vaults": ranked,
        "total": len(ranked),
    }


@router.get("/api/leaderboard/traders")
async def top_traders(limit: int = Query(default=5, ge=1, le=50)):
    vaults = _enrich_featured_vaults()
    creator_map: dict[str, dict] = {}
    for v in vaults:
        creator = v.get("creator", "Unknown")
        if creator not in creator_map:
            creator_map[creator] = {
                "address": creator,
                "vault_count": 0,
                "total_tvl": 0.0,
                "best_return_7d": 0.0,
                "total_clones": 0,
                "total_followers": 0,
            }
        entry = creator_map[creator]
        entry["vault_count"] += 1
        entry["total_tvl"] += v.get("total_deposited", 0)
        entry["best_return_7d"] = max(entry["best_return_7d"], v.get("return_7d", 0))
        entry["total_clones"] += v.get("clone_count", 0)
        entry["total_followers"] += v.get("follower_count", 0)

    traders = sorted(creator_map.values(), key=lambda t: t["best_return_7d"], reverse=True)
    for idx, t in enumerate(traders):
        t["rank"] = idx + 1

    return {
        "traders": traders[:limit],
        "total": len(traders),
    }
