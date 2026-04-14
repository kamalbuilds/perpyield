# PerpYield Verification Skill - Dangerous Illusions Catalog

## CRITICAL: Always Verify These "Working" Features

This document catalogs "illusions" - features that appear to work in UI but are actually fake/stub implementations. These are DANGEROUS for hackathon judging.

---

## Known Illusions (Found 2026-04-15)

### 1. Close Position Button
**Appearance:** Button exists, clickable, shows "Close Position" modal  
**Reality:** `console.log('Closing position...')` - NO API call  
**Location:** `frontend/src/app/page.tsx:79`  
**Fix Required:** Call `POST /api/v1/positions/{id}/close` or `PacificaClient.create_market_order(reduce_only=True)`

### 2. Add Margin Button
**Appearance:** Button exists in position detail  
**Reality:** `console.log('Adding margin...')` - NO API call  
**Location:** `frontend/src/app/page.tsx:85`  
**Fix Required:** Call `POST /api/v1/positions/{id}/margin` with real amount

### 3. TP/SL (Take Profit/Stop Loss) Buttons
**Appearance:** TP/SL inputs exist, buttons clickable  
**Reality:** `console.log('Setting TP/SL...')` - NO API call  
**Location:** `frontend/src/app/page.tsx:89`  
**Fix Required:** Call `PacificaClient.set_tpsl()` or `POST /api/v1/positions/{id}/tpsl`

### 4. Deposit/Withdraw Flow
**Appearance:** Forms work, "Success" toast shown  
**Reality:** Hardcoded "demo" wallet address, NO real SPL transfer  
**Location:** 
- `frontend/src/app/strategy/page.tsx:114` (deposit)
- `frontend/src/app/strategy/page.tsx:136` (withdraw)
- `backend/api/vault_routes.py` - returns hardcoded success for "demo"  
**Fix Required:** 
1. Get real wallet address from connected wallet
2. Call `PacificaClient.deposit_to_lake()` for deposit
3. Call `PacificaClient.withdraw_from_lake()` for withdraw

### 5. Trade History Display
**Appearance:** "Trades: 1" shows on position  
**Reality:** "Trade history available via API" placeholder text instead of real data  
**Location:** `frontend/src/app/page.tsx` - Trade history section  
**Fix Required:** Call `GET /api/v1/positions/{id}/trades` and render actual trades

### 6. WebSocket Price Connection
**Appearance:** Shows "Live Data: Connected" with green dot  
**Reality:** Actually failing silently, falls back to `entry_price`  
**Location:** `frontend/src/hooks/usePositions.ts` - WebSocket connection  
**Fix Required:** Fix backend WS endpoint or use polling fallback with real-time updates

### 7. Strategy Page (Deposit/Withdraw)
**Appearance:** Page loads sometimes  
**Reality:** Crashes on API errors (422/502), no error boundaries  
**Location:** `frontend/src/app/strategy/page.tsx`  
**Fix Required:** Add error boundaries, handle API response shape mismatches

### 8. Leaderboard 90d Filter
**Appearance:** "90d" option exists in dropdown  
**Reality:** Backend only accepts "7d|30d|all", 422 error on "90d"  
**Location:** `frontend/src/app/leaderboard/page.tsx:10`  
**Fix Required:** Change "90d" to "all" or add backend support

### 9. Monthly Returns Display
**Appearance:** Shows monthly breakdown  
**Reality:** All months show +0.00% despite negative overall return (calculation bug)  
**Location:** `frontend/src/components/BacktestResults.tsx`  
**Fix Required:** Fix monthly return calculation/display

### 10. Position P&L Updates
**Appearance:** P&L changes periodically  
**Reality:** Frontend calculates locally using `entry_price`, NOT real-time mark price  
**Location:** `frontend/src/app/page.tsx` - Position card P&L  
**Fix Required:** Use real-time mark price from Pacifica API or WebSocket

---

## Verification Checklist

Before claiming ANY feature works, verify:

- [ ] **Network tab shows real API call** - Not just console.log
- [ ] **Response contains real data** - Not hardcoded values
- [ ] **Database/state actually changes** - Refresh page, data persists
- [ ] **Real blockchain transaction** - For deposits/withdraws/trades
- [ ] **Error handling works** - Test with invalid inputs, shows error not crash
- [ ] **Wallet address is real** - Not "demo", "test", or hardcoded

---

## Red Flags - Investigate Immediately

1. `console.log('Doing X...')` in event handlers
2. Hardcoded strings like "demo", "test", "placeholder"
3. Success toasts without API calls
4. "Available via API" text instead of actual data
5. Mock data files in `/mocks/`, `/fixtures/`, `/fake/`
6. `setTimeout()` simulating async operations
7. `Math.random()` generating fake results
8. Comments like `// TODO: implement`, `// FIXME`, `// mock`

---

## Backend Real Methods Available

From `backend/pacifica/client.py`:
- `create_market_order(symbol, side, quantity, reduce_only=False)` - Real trading
- `set_tpsl(position_id, take_profit=None, stop_loss=None)` - Set TP/SL
- `deposit_to_lake(vault_id, amount)` - Real SPL deposit
- `withdraw_from_lake(vault_id, amount)` - Real SPL withdraw
- `get_account_balance()` - Real balance query
- `get_positions()` - Real position fetch

---

## Testing Realness

To verify a feature is real:

```bash
# 1. Check network tab in browser
curl -s "https://perpyield-api-production.up.railway.app/api/v1/positions" | jq

# 2. Verify on-chain (for Solana)
solana balance <wallet-address> --url https://api.devnet.solana.com

# 3. Check Pacifica testnet explorer for transactions
# https://testnet.pacificascan.com/address/<wallet>

# 4. Refresh page - data should persist (not reset)
```

---

## Agent Instructions

When fixing illusions:
1. **Never use console.log for actions** - Always call real API
2. **Never hardcode addresses** - Use connected wallet
3. **Never show success without confirmation** - Wait for API/blockchain response
4. **Add error boundaries** - Prevent page crashes
5. **Remove placeholder text** - Show real data or loading state
6. **Test end-to-end** - Verify with real transactions

---

## Updated
Last verified: 2026-04-15
Found 10 illusions, 0 fixed
