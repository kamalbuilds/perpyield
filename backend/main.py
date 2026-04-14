from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fnmatch import fnmatch
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

import config

_cors_patterns = [p.strip() for p in config.CORS_ORIGINS.split(",") if p.strip()]
_cors_methods = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
_cors_headers = "Accept, Authorization, Content-Type, X-Requested-With, X-Api-Key"


class WildcardCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        allowed = bool(origin) and any(fnmatch(origin, p) for p in _cors_patterns)

        if request.method == "OPTIONS" and allowed:
            return StarletteResponse(
                status_code=200,
                headers={
                    "access-control-allow-origin": origin,
                    "access-control-allow-credentials": "true",
                    "access-control-allow-methods": _cors_methods,
                    "access-control-allow-headers": _cors_headers,
                    "access-control-max-age": "600",
                    "vary": "Origin",
                },
            )

        response = await call_next(request)

        if allowed:
            response.headers["access-control-allow-origin"] = origin
            response.headers["access-control-allow-credentials"] = "true"
            response.headers["vary"] = "Origin"

        return response


from pacifica.client import PacificaClient, sf
from pacifica.websocket_client import PacificaWebSocket
from strategy.funding_scanner import FundingScanner
from strategy.delta_neutral import DeltaNeutralStrategy
from strategy.rebalancer import Rebalancer
from strategy.vault_manager import VaultManager
from strategy.backtester import Backtester

from api.market_routes import router as market_router
from api.account_routes import router as account_router
from api.order_routes import router as order_router
from api.lake_routes import router as lake_routes
from api.strategy_routes import router as strategy_router
from api.vault_routes import router as vault_router
from api.backtest_routes import router as backtest_router
from api.leaderboard_routes import router as leaderboard_router
from api.social_routes import router as social_router
from api.risk_routes import router as risk_router
from ai_advisor.api_routes import router as ai_router

logger = logging.getLogger(__name__)

_client: Optional[PacificaClient] = None
_scanner: Optional[FundingScanner] = None
_strategy: Optional[DeltaNeutralStrategy] = None
_rebalancer: Optional[Rebalancer] = None
_vault_manager: Optional[VaultManager] = None
_backtester: Optional[Backtester] = None
_ws_clients: list[WebSocket] = []


def get_client() -> Optional[PacificaClient]:
    """Get Pacifica client - returns None if not configured."""
    global _client
    if _client is None:
        # Only initialize if we have required config
        if not config.PACIFICA_PRIVATE_KEY:
            logger.warning("PACIFICA_PRIVATE_KEY not set, client unavailable")
            return None
        try:
            _client = PacificaClient(
                private_key=config.PACIFICA_PRIVATE_KEY,
                testnet=config.PACIFICA_TESTNET,
                builder_code=config.PACIFICA_BUILDER_CODE,
                agent_wallet_key=config.PACIFICA_AGENT_WALLET,
            )
        except Exception as e:
            logger.error(f"Failed to initialize PacificaClient: {e}")
            return None
    return _client


def get_scanner() -> Optional[FundingScanner]:
    global _scanner
    if _scanner is None:
        client = get_client()
        if client:
            _scanner = FundingScanner(client)
    return _scanner


def get_strategy() -> Optional[DeltaNeutralStrategy]:
    global _strategy
    if _strategy is None:
        client = get_client()
        if client:
            _strategy = DeltaNeutralStrategy(client)
    return _strategy


def get_rebalancer() -> Optional[Rebalancer]:
    global _rebalancer
    if _rebalancer is None:
        client = get_client()
        if client:
            _rebalancer = Rebalancer(client)
    return _rebalancer


def get_vault_manager() -> Optional[VaultManager]:
    global _vault_manager
    if _vault_manager is None:
        client = get_client()
        if client:
            _vault_manager = VaultManager(client)
    return _vault_manager


def get_backtester() -> Optional[Backtester]:
    global _backtester
    if _backtester is None:
        client = get_client()
        if client:
            _backtester = Backtester(client)
    return _backtester


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize services lazily - don't fail if no config
    logger.info("PerpYield backend starting...")
    yield
    # Shutdown cleanup
    from api.strategy_routes import get_strategy_task, get_rebalancer_task
    st = get_strategy_task()
    rt = get_rebalancer_task()
    if st and not st.done():
        st.cancel()
    if rt and not rt.done():
        rebalancer = get_rebalancer()
        if rebalancer:
            rebalancer.stop_loop()
        rt.cancel()
    if _client:
        await _client.aclose()
    logger.info("PerpYield backend shutdown")


app = FastAPI(title="PerpYield API", version="2.0.0", lifespan=lifespan)

app.add_middleware(WildcardCORSMiddleware)

# New modular routes (prefixed under /api/v1)
app.include_router(market_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(order_router, prefix="/api/v1")
app.include_router(lake_routes, prefix="/api/v1")

# Legacy routes (keep /api prefix for backward compat)
app.include_router(strategy_router)
app.include_router(vault_router)
app.include_router(backtest_router)
app.include_router(leaderboard_router)
app.include_router(social_router)
app.include_router(risk_router)
app.include_router(ai_router)


@app.get("/api/health")
async def health():
    """Health check endpoint - always returns OK even if client not configured."""
    client = get_client()
    return {
        "status": "ok",
        "service": "perpyield-backend",
        "version": "2.0.0",
        "timestamp": int(time.time() * 1000),
        "client_configured": client is not None,
        "testnet": config.PACIFICA_TESTNET,
    }


@app.get("/health")
async def health_simple():
    return {"status": "ok", "service": "perpyield-backend"}


# Legacy endpoints for backward compatibility - handle missing client gracefully

@app.get("/api/markets")
async def get_markets():
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pacifica client not configured")
    try:
        markets = await client.get_markets()
        return [m.model_dump() for m in markets]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/prices")
async def get_prices():
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pacifica client not configured")
    try:
        prices = await client.get_prices()
        return [p.model_dump() for p in prices]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/funding/rates")
async def get_funding_rates():
    client = get_client()
    scanner = get_scanner()
    if not client or not scanner:
        raise HTTPException(status_code=503, detail="Pacifica client not configured")
    try:
        all_rates = await scanner.fetch_all_funding_rates()
        ranked = scanner.rank_by_funding_rate(all_rates)
        results = []
        for r in ranked:
            apy = scanner.rate_to_apy(r["funding_rate"])
            results.append({
                **r,
                "annualized_apy": round(apy, 4),
            })
        return results
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/funding/history/{symbol}")
async def get_funding_history(symbol: str, hours: int = Query(default=168, ge=1, le=8760)):
    client = get_client()
    scanner = get_scanner()
    if not client or not scanner:
        raise HTTPException(status_code=503, detail="Pacifica client not configured")
    try:
        history = await scanner.track_funding_history(symbol, limit=hours)
        return {
            "symbol": history.symbol,
            "rates": history.rates,
            "avg_rate_24h": history.avg_rate_24h,
            "avg_rate_7d": history.avg_rate_7d,
            "positive_rate_pct": history.positive_rate_pct,
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/orderbook/{symbol}")
async def get_orderbook(symbol: str, agg_level: int = Query(default=1, ge=1)):
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pacifica client not configured")
    try:
        book = await client.get_orderbook(symbol, agg_level)
        return book.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/klines/{symbol}")
async def get_klines(
    symbol: str,
    interval: str = Query(default="1h"),
    days: int = Query(default=7, ge=1, le=365),
):
    client = get_client()
    if not client:
        raise HTTPException(status_code=503, detail="Pacifica client not configured")
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000
    try:
        candles = await client.get_klines(symbol, interval, start_ms, end_ms)
        return [c.model_dump() for c in candles]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# WebSocket for real-time prices

@app.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    client = get_client()
    if not client:
        await websocket.send_json({"error": "Pacifica client not configured"})
        await websocket.close()
        return
    try:
        while True:
            try:
                prices = await client.get_prices()
                funding_rates = await client.get_funding_rates()
                await websocket.send_json({
                    "type": "price_update",
                    "timestamp": int(time.time() * 1000),
                    "prices": [p.model_dump() for p in prices],
                    "funding_rates": funding_rates,
                })
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WS price relay error: {e}")
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
    )
