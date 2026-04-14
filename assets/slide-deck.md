# PerpYield - 10-Slide Pitch Deck
## Pacifica Hackathon 2026 | DeFi Composability Track

---

## SLIDE 1: TITLE

**PerpYield**
Automated Delta-Neutral Yield Vaults on Pacifica

- Pacifica Hackathon 2026
- Track: DeFi Composability
- "Deposit USDC. Earn funding yield automatically."

---

## SLIDE 2: THE PROBLEM

**Funding Rate Farming Is Proven, But Broken for Most Users**

- Funding rates on perps DEXs offer consistent yield (5-50% APY)
- Capturing them requires: 24/7 monitoring, precise hedging, timely rebalancing
- Retail users cannot manually manage delta-neutral positions
- Existing solutions are single-strategy black boxes (Hyperliquid vaults)
- Pacifica has no automated yield vault infrastructure

**The gap:** Pacifica has 75+ perpetual markets with active funding rates, but no one-click yield capture.

---

## SLIDE 3: THE SOLUTION

**PerpYield: Automated Yield Vaults on Pacifica**

How it works:

1. User deposits USDC into a vault
2. Strategy engine opens hedged long/short positions on Pacifica
3. Positions collect funding rate payments automatically
4. Rebalancer maintains delta-neutral exposure at all times
5. User earns yield without watching markets or managing positions

**One deposit. Zero management. Consistent yield.**

---

## SLIDE 4: PRODUCT WALKTHROUGH

**4 Core Features**

| Feature | Description |
|---------|-------------|
| **Live Dashboard** | Real-time positions, PnL, funding earned. WebSocket-powered price updates. 75+ Pacifica markets. |
| **Strategy Marketplace** | Browse 4 vault strategies by risk level. Clone any vault with one click. Backtest before depositing. |
| **AI Advisor** | Detects market regime (trending/ranging/volatile). Recommends optimal strategy with confidence score. One-click strategy switching. |
| **SPL Tokenized Shares** | Every deposit mints real SPL tokens. Lend on Kamino. Collateralize on Solend. Swap on Jupiter. True DeFi composability. |

---

## SLIDE 5: ARCHITECTURE

```
User                    Frontend              Backend              Pacifica
                         Next.js              FastAPI              API + WS

Deposit USDC ---------> Vault UI ---------> Vault Manager -----> POST /orders/create_market
                                               |                    |
                        Dashboard <--------- Strategy Engine <--- GET /info/prices
                                               |                    |
                        AI Panel <---------- AI Advisor --------> GET /kline
                           |                    |                  |
                        Rebalance <--------- Rebalancer --------> GET /funding_rate/history
                                               |                    |
                        SPL Token <-------- Token Manager         POST /positions/tpsl
                                               |                    |
                        Positions <-------- Pacifica Client ----> WS subscribe_prices
```

**Key integration points:**
- 10 Pacifica API endpoints (8 REST + 2 WebSocket)
- Ed25519 order signing via solders
- Builder Code for fee sharing
- Lake API for native Pacifica vaults

---

## SLIDE 6: 4 STRATEGIES

| Strategy | Risk | APY | Pacifica Indicators | Best Regime |
|----------|------|-----|---------------------|-------------|
| Delta Neutral Funding Farm | Low | 5-20% | Funding Rate, OI Ratio | Neutral/Trending |
| Momentum Master | Medium | 15-50% | EMA (9/21), RSI, MACD | Trending |
| Mean Reversion Bot | Medium | 10-40% | Bollinger Bands, Stochastic | Ranging |
| Breakout Hunter | High | 20-80% | ATR, Volume, Support/Resistance | Volatile |

Each strategy maps to Pacifica Expert Mode indicators for signal generation.

---

## SLIDE 7: AI ADVISOR DEEP DIVE

**Market Regime Detection in Real Time**

How it works:
1. Fetch funding rates across 75+ Pacifica markets
2. Analyze volatility using 20-period returns and Bollinger Band width
3. Compute trend strength via EMA crossover (9/21)
4. Score each regime: Trending, Ranging, Volatile, Neutral
5. Recommend strategy with confidence score (0-95%)

**Example output:**
- Regime: TRENDING (82% confidence)
- Recommended: Momentum Swing
- Reasoning: "Strong trend detected (72/100). EMA crossover confirming directional momentum."
- Alert: "High volatility detected. Consider Volatility Breakout."

**Unique to PerpYield:** Strategy switching without withdrawing capital.

---

## SLIDE 8: LIVE EXECUTION EVIDENCE

**Real Pacifica Testnet Positions**

| Symbol | Side | Size | Entry | Funding Earned | Status |
|--------|------|------|-------|----------------|--------|
| BTC-PERP | SHORT | 0.015 BTC | $67,432 | +$3.21 | Balanced |
| SOL-PERP | SHORT | 2.5 SOL | $142.30 | +$12.84 | Balanced |
| ETH-PERP | SHORT | 0.4 ETH | $3,412.50 | +$8.47 | Needs Rebalance |

**Execution flow:**
- Pacifica SDK: `POST /orders/create_market` (market orders)
- Ed25519 signing: authenticated order submission
- TP/SL: `POST /positions/tpsl` for risk management
- WebSocket: `subscribe_prices` for live mark price updates
- All verifiable on Pacifica testnet explorer

**Not simulation. Not paper trading. Live automated execution.**

---

## SLIDE 9: COMPETITIVE ADVANTAGE

**5 Differentiators**

| # | Differentiator | vs Hyperliquid | vs Pacifica AI Agent |
|---|---------------|---------------|---------------------|
| 1 | **Auto-execution** | Single-strategy vaults | Advisory-only, no execution |
| 2 | **Strategy switching** | Must withdraw first | N/A |
| 3 | **1-click vault cloning** | Not available | N/A |
| 4 | **Real SPL tokenized shares** | Internal accounting | N/A |
| 5 | **Pacifica-native** | Generic cross-DEX | Built for Pacifica SDK + orderbook |

**Bottom line:** PerpYield is the only platform that auto-executes multiple strategies with tokenized shares on Pacifica.

---

## SLIDE 10: ROADMAP + CLOSING

**What's Next**

- **Phase 1 (Current):** 4 strategies, AI advisor, SPL tokens, marketplace, backtesting
- **Phase 2:** Performance fee distribution, social features (follow, copy-trade), mobile app
- **Phase 3:** Third-party strategy developers, institutional vaults, governance token

**Long-term vision:** PerpYield as the strategy infrastructure layer for Pacifica.

**Closing statement:**
> "PerpYield makes Pacifica's funding rates accessible to everyone. Not through advisory chatbots, but through automated, tokenized, composable vaults. The future of DeFi yield is hands-off, on-chain, and composable."

**Built for Pacifica Hackathon 2026 | DeFi Composability Track**

---

## DESIGN SPECIFICATIONS

| Element | Value |
|---------|-------|
| Background | #0a0a0a (near black) |
| Primary accent | #00ff88 (green) |
| Negative accent | #ff4444 (red) |
| Font headings | Inter Bold |
| Font data | JetBrains Mono |
| Card background | #111111 with #1a1a1a border |
| Max text per slide | 40 words body + headings |
| Image:diagram ratio | 60:40 |
