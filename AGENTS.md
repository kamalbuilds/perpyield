# PerpYield Agent Instructions

## CRITICAL: No Fake/Mock Code Allowed

This project has ZERO TOLERANCE for fake implementations. Every feature must:
- Call REAL APIs (not console.log)
- Use REAL blockchain transactions (not state updates only)
- Show REAL data (not placeholders)

See `VERIFICATION_SKILL.md` for the full catalog of illusions that were fixed.

---

## Architecture

**Frontend:** Next.js 16.2.3 + React + TypeScript + Tailwind CSS + @solana/wallet-adapter
- Location: `/frontend/`
- Deployed to: https://kuber-bnb.vercel.app
- Environment: Production build via Vercel

**Backend:** Python + FastAPI + Pacifica Client
- Location: `/backend/`
- Deployed to: https://perpyield-api-production.up.railway.app
- Real Pacifica testnet integration with live trading

---

## Backend API Structure

All routes mounted in `main.py`:

| Endpoint | File | Description |
|----------|------|-------------|
| `/api/positions` | `strategy_routes.py` | List positions (live from Pacifica) |
| `/api/positions/close` | `strategy_routes.py` | Close position (real market order) |
| `/api/positions/margin` | `strategy_routes.py` | Add margin to position |
| `/api/positions/tpsl` | `strategy_routes.py` or `order_routes.py` | Set TP/SL |
| `/api/orders/*` | `order_routes.py` | Order management |
| `/api/vault/deposit` | `vault_routes.py` | Deposit to vault (real SPL) |
| `/api/vault/withdraw` | `vault_routes.py` | Withdraw from vault (real SPL) |
| `/api/leaderboard/*` | `leaderboard_routes.py` | Vault rankings |
| `/api/account/*` | `account_routes.py` | User data, trade history |

---

## Pacifica Client Methods (Real Trading)

From `pacifica/client.py`:

```python
# Orders
create_market_order(symbol, side, amount, reduce_only=False)
create_limit_order(symbol, side, price, amount, reduce_only=False, tif="GTC")
cancel_order(symbol, order_id=None, client_order_id=None)

# Position Management
set_tpsl(symbol, side, take_profit=None, stop_loss=None, tp_price=None, sl_price=None)
add_margin(symbol, side, amount, isolated=False)
set_leverage(symbol, leverage)

# Vault/Lake Operations (SPL Tokens)
create_lake(nickname=None)
deposit_to_lake(lake_address, amount)
withdraw_from_lake(lake_address, shares)

# Data Fetching
get_positions(account=None)
get_trade_history(account=None, limit=50)
get_funding_history(account=None, limit=50)
get_balances(account=None)
```

---

## Frontend Key Components

| Component | Purpose |
|-----------|---------|
| `PriceContext.tsx` | WebSocket + polling price feed (real mark prices) |
| `usePositions.ts` | Fetch and enrich positions with live P&L |
| `useTradeHistory.ts` | Paginated trade history fetching |
| `PositionTable.tsx` | Position list with actions (close, margin, TP/SL) |
| `ClosePositionModal.tsx` | Close position UI |
| `AddMarginModal.tsx` | Add margin UI |
| `TPSLModal.tsx` | Set TP/SL UI |
| `ErrorBoundary.tsx` | Catch runtime errors gracefully |

---

## Real Features Checklist (All Fixed ✅)

- [x] Close Position → Real Pacifica market order with reduce_only
- [x] Add Margin → Real margin addition via Pacifica
- [x] TP/SL → Real TP/SL orders on Pacifica
- [x] Deposit → Real SPL transfer via `deposit_to_lake()`
- [x] Withdraw → Real SPL transfer via `withdraw_from_lake()`
- [x] Trade History → Real trade data from Pacifica API
- [x] Position P&L → Real mark prices from WebSocket or 5s polling
- [x] Leaderboard → Real performance data, proper filtering
- [x] Monthly Returns → Correct calculation (not all +0.00%)
- [x] Error Handling → No page crashes on API errors

---

## Environment Variables

**Frontend (Vercel):**
```
NEXT_PUBLIC_API_URL=https://perpyield-api-production.up.railway.app
NEXT_PUBLIC_WS_URL=wss://perpyield-api-production.up.railway.app
NEXT_PUBLIC_SOLANA_RPC_URL=https://api.devnet.solana.com
```

**Backend (Railway):**
```
PACIFICA_PRIVATE_KEY=<testnet trading key>
PACIFICA_TESTNET=true
CORS_ORIGINS=*
```

---

## Testing Realness

Before claiming any feature works:
1. Check browser Network tab - must show real API call
2. Verify response contains real data (not hardcoded)
3. For trades/deposits: verify on Pacifica testnet explorer
4. Refresh page - data must persist
5. Test error cases - must show error UI not crash

**Pacifica Testnet Explorer:**
https://testnet.pacificascan.com/address/<wallet_address>

---

## Commit History

Key commits:
- `6632f1d` - "Fix all fake/illusion implementations - real trading now works"

---

## Red Flags (Never Allow)

1. `console.log()` instead of API calls
2. Hardcoded "demo", "test", "placeholder" strings
3. Success toasts without waiting for API response
4. "Available via API" placeholder text
5. Mock data in `/mocks/`, `/fixtures/`
6. `setTimeout()` simulating async
7. `Math.random()` for fake results
8. `// TODO: implement`, `// FIXME`, `// mock` comments

---

## Deployment

**Backend:**
```bash
cd backend
railway up --detach -m "Description"
```

**Frontend:**
```bash
cd frontend
vercel --prod
```

---

Last updated: 2026-04-15
