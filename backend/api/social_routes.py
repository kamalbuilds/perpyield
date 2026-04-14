from __future__ import annotations

import json
import time
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["social"])

DATA_DIR = Path("data")


def _social_path(vault_id: str) -> Path:
    return DATA_DIR / f"{vault_id}_social.json"


def _follows_path(user_address: str) -> Path:
    return DATA_DIR / f"follows_{user_address}.json"


def _load_social(vault_id: str) -> dict:
    p = _social_path(vault_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {
        "vault_id": vault_id,
        "clone_count": 0,
        "follower_count": 0,
        "view_count": 0,
        "weekly_depositors": 0,
        "followers": [],
        "created_at": int(time.time() * 1000),
    }


def _save_social(vault_id: str, data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _social_path(vault_id)
    p.write_text(json.dumps(data, indent=2))


def _load_follows(user_address: str) -> dict:
    p = _follows_path(user_address)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {
        "user_address": user_address,
        "following_vaults": [],
        "updated_at": int(time.time() * 1000),
    }


def _save_follows(user_address: str, data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    p = _follows_path(user_address)
    data["updated_at"] = int(time.time() * 1000)
    p.write_text(json.dumps(data, indent=2))


class FollowVaultRequest(BaseModel):
    user_address: str
    vault_id: str


class UnfollowVaultRequest(BaseModel):
    user_address: str
    vault_id: str


class TrackViewRequest(BaseModel):
    vault_id: str


class TrackDepositRequest(BaseModel):
    vault_id: str


@router.post("/api/social/follow-vault")
async def follow_vault(req: FollowVaultRequest):
    social = _load_social(req.vault_id)
    if req.user_address not in social.get("followers", []):
        social.setdefault("followers", []).append(req.user_address)
        social["follower_count"] = len(social["followers"])
        _save_social(req.vault_id, social)

    follows = _load_follows(req.user_address)
    if req.vault_id not in follows["following_vaults"]:
        follows["following_vaults"].append(req.vault_id)
        _save_follows(req.user_address, follows)

    return {
        "status": "followed",
        "vault_id": req.vault_id,
        "follower_count": social["follower_count"],
    }


@router.post("/api/social/unfollow-vault")
async def unfollow_vault(req: UnfollowVaultRequest):
    social = _load_social(req.vault_id)
    if req.user_address in social.get("followers", []):
        social["followers"].remove(req.user_address)
        social["follower_count"] = len(social["followers"])
        _save_social(req.vault_id, social)

    follows = _load_follows(req.user_address)
    if req.vault_id in follows["following_vaults"]:
        follows["following_vaults"].remove(req.vault_id)
        _save_follows(req.user_address, follows)

    return {
        "status": "unfollowed",
        "vault_id": req.vault_id,
        "follower_count": social["follower_count"],
    }


@router.get("/api/social/following")
async def get_following(user_address: str):
    follows = _load_follows(user_address)
    vault_details = []
    for vid in follows["following_vaults"]:
        social = _load_social(vid)
        vault_details.append({
            "vault_id": vid,
            "follower_count": social.get("follower_count", 0),
            "clone_count": social.get("clone_count", 0),
        })
    return {
        "user_address": user_address,
        "following": vault_details,
        "total_following": len(vault_details),
    }


@router.post("/api/social/track-view")
async def track_view(req: TrackViewRequest):
    social = _load_social(req.vault_id)
    social["view_count"] = social.get("view_count", 0) + 1
    _save_social(req.vault_id, social)
    return {"status": "tracked", "view_count": social["view_count"]}


@router.post("/api/social/track-depositor")
async def track_depositor(req: TrackDepositRequest):
    social = _load_social(req.vault_id)
    social["weekly_depositors"] = social.get("weekly_depositors", 0) + 1
    _save_social(req.vault_id, social)
    return {"status": "tracked", "weekly_depositors": social["weekly_depositors"]}


@router.get("/api/social/vault-stats/{vault_id}")
async def vault_social_stats(vault_id: str):
    social = _load_social(vault_id)
    return social


@router.get("/api/social/share/{vault_id}")
async def share_vault(vault_id: str):
    social = _load_social(vault_id)
    from strategy.vault_manager import STRATEGY_REGISTRY

    on_disk = None
    vault_file = DATA_DIR / f"{vault_id}.json"
    if vault_file.exists():
        try:
            on_disk = json.loads(vault_file.read_text())
        except Exception:
            pass

    name = "Unknown Vault"
    strategy_name = "Unknown"
    pnl_pct = 0.0
    tvl = 0.0
    if on_disk:
        name = on_disk.get("vault_name", vault_id)
        sid = on_disk.get("strategy_id", "delta_neutral")
        strategy_name = STRATEGY_REGISTRY.get(sid, {}).get("name", "Unknown")
        total_deposited = on_disk.get("total_deposited", 0)
        tvl = total_deposited
        if total_deposited > 0:
            history = on_disk.get("performance_history", [])
            if history:
                current = history[-1].get("vault_value", total_deposited)
                pnl_pct = ((current - total_deposited) / total_deposited) * 100
                tvl = current

    text = f"I'm earning {pnl_pct:.1f}% APY with {name} on PerpYield! Strategy: {strategy_name}. TVL: ${tvl:,.0f}. #PerpYield #DeFi #FundingRate"

    return {
        "vault_id": vault_id,
        "name": name,
        "pnl_pct": round(pnl_pct, 2),
        "tvl": round(tvl, 2),
        "clone_count": social.get("clone_count", 0),
        "follower_count": social.get("follower_count", 0),
        "share_text": text,
        "twitter_url": f"https://twitter.com/intent/tweet?text={text}",
    }
