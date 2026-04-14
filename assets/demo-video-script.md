# PerpYield Demo Video Script

| Field | Value |
|-------|-------|
| Title | PerpYield - Automated Delta-Neutral Yield Vaults on Pacifica |
| Length | 3:00 |
| Audience | Pacifica Hackathon Judges (DeFi Composability Track) |
| Resolution | 1920x1080, 30fps |

---

## SCENE 1: THE PROBLEM (0:00-0:20)

**VISUAL:** Dark screen. Text fades in:

> "Funding rate farming works. But doing it manually is broken."

Quick cuts: a trader staring at spreadsheets, funding rates flashing, positions drifting out of balance, missed rebalance opportunities.

Then: PerpYield logo animates in.

> "PerpYield: Automated Delta-Neutral Yield on Pacifica"

**VOICEOVER:**
> "Perpetual funding rates are one of the most consistent yield sources in DeFi. But capturing them requires constant monitoring, precise hedging, and timely rebalancing. PerpYield automates all of it on Pacifica."

**TEXT OVERLAYS** (1.5s each):
- "75+ Markets"
- "Auto-Rebalancing"
- "Real Testnet Execution"

---

## SCENE 2: LIVE DASHBOARD (0:20-0:50)

**VISUAL:** Screen recording of dashboard at `/`.

**ACTIONS:**

1. Dashboard loads. Four stat cards populate with real data:
   - Active Positions: 3
   - Unrealized PnL: +$47.82
   - Total Funding Earned: $234.50
   - WebSocket: Connected (green pulse)

2. Position table fills with live Pacifica testnet positions:
   - BTC-PERP: SHORT, 0.015 BTC, entry $67,432, funding +$3.21
   - SOL-PERP: SHORT, 2.5 SOL, entry $142.30, funding +$12.84
   - ETH-PERP: SHORT, 0.4 ETH, entry $3,412.50, funding +$8.47

3. Hover over SOL-PERP row: mark price updates in real time via WebSocket

4. Green "LIVE" indicator pulses next to Active Positions header

**VOICEOVER:**
> "Real positions. Real funding. Real Pacifica testnet execution. The dashboard shows live positions with mark prices updating via WebSocket. Every funding payment is tracked and displayed. No simulation, no paper trading."

**TEXT OVERLAY:** "Live Pacifica Testnet Positions"

---

## SCENE 3: STRATEGY ENGINE (0:50-1:20)

**VISUAL:** Navigate to `/strategy`.

**ACTIONS:**

1. Strategy page loads with vault controls. Green "Running" pulse visible.

2. Strategy configuration panel shows:
   - Min Funding Threshold: 0.01%
   - Max Leverage: 3x
   - Rebalance Interval: 5 min

3. Delta Summary table loads with per-symbol exposure:
   - BTC-PERP: Long $1,012, Short $1,008, Net Delta +$4 (0.4%), Balanced
   - SOL-PERP: Long $355, Short $350, Net Delta +$5 (1.4%), Balanced
   - ETH-PERP: Long $1,365, Short $1,360, Net Delta +$5 (0.4%), Needs Rebalance

4. Click "Start Vault" - strategy activates, positions begin opening

5. Show deposit flow: type "100" USDC, click Deposit, success toast

**VOICEOVER:**
> "The delta-neutral strategy engine pairs offsetting long and short positions to maintain near-zero market exposure. When funding rates are positive, the vault shorts the overleveraged side. When negative, it goes long. The rebalancer keeps positions market-neutral at all times, configurable to your thresholds."

**TEXT OVERLAY:** "Delta-Neutral. Auto-Rebalanced. Market-Agnostic."

**KEY DIFFERENTIATOR:** "Unlike Pacifica's AI Agent (advisory-only), PerpYield auto-executes trades"

---

## SCENE 4: AI ADVISOR (1:20-1:50)

**VISUAL:** AI advisor data loading on strategy page.

**ACTIONS:**

1. AI market analysis panel appears (from `/api/ai/market-analysis`):
   - Current regime: "TRENDING" with confidence badge "82%"
   - Recommended strategy: "Momentum Swing"
   - Reasoning: "Strong trend detected (strength: 72/100). EMA crossover confirming directional momentum."
   - Top funding symbols: BTC-PERP (+0.012%, 10.8% APY), SOL-PERP (+0.008%, 7.2% APY)
   - Trending symbols: ETH-PERP (trend strength: 68/100, bullish)

2. Funding rate heatmap visible showing 75+ markets ranked by annualized APY

3. Alert notification: "High volatility detected. Consider switching to Volatility Breakout."

4. Click "Apply Recommendation" - strategy switches instantly without withdrawal

**VOICEOVER:**
> "Our AI advisor monitors Pacifica across 75+ markets in real time. It detects the current market regime: trending, ranging, or volatile. Based on the regime, it recommends the optimal strategy with a confidence score. One click applies the recommendation, switching strategies without withdrawing capital. This is a first on Pacifica."

**TEXT OVERLAY:** "AI-Powered Regime Detection"

---

## SCENE 5: MARKETPLACE (1:50-2:15)

**VISUAL:** Navigate to `/marketplace`.

**ACTIONS:**

1. Page loads showing 4 vault cards in 2-column grid:
   - Delta Neutral Funding Farm (Low risk, 5-20% APY)
   - Momentum Master (Medium risk, 15-50% APY)
   - Mean Reversion Bot (Medium risk, 10-40% APY)
   - Breakout Hunter (High risk, 20-80% APY)

2. Click risk filter "Low" - only Delta Neutral shows

3. Hover over Delta Neutral card: risk badge, APY range, 7d/30d performance

4. Click "Clone Vault" on Momentum Master - green success toast: "Vault cloned!"

5. Click "Backtest" - equity curve and Sharpe ratio appear

**VOICEOVER:**
> "The marketplace lets users browse strategies filtered by risk level. Each vault shows expected APY, historical performance, and risk classification. Clone any vault with one click to create your own customized version. Backtest before you deposit."

**TEXT OVERLAY:** "1-Click Clone. Backtest Before Deposit."

---

## SCENE 6: BACKTESTING (2:15-2:35)

**VISUAL:** Navigate to `/backtest`.

**ACTIONS:**

1. Backtest form: select strategy "Delta Neutral", symbol "BTC", period "30d"

2. Click "Run Backtest" - loading animation

3. Results panel appears:
   - Equity curve climbing steadily upward
   - Total Return: +12.4%
   - Annualized APY: 15.1%
   - Sharpe Ratio: 1.82
   - Max Drawdown: -3.2%
   - Win Rate: 72%
   - Total Trades: 156

4. Comparison chart: Delta Neutral vs Momentum Swing vs Buy & Hold

**VOICEOVER:**
> "Before committing capital, backtest any strategy on historical Pacifica funding data. The engine computes Sharpe ratio, max drawdown, win rate, and generates a full equity curve. Compare strategies side by side to find the best fit for your risk profile."

**TEXT OVERLAY:** "Backtest. Compare. Decide."

---

## SCENE 7: SPL TOKEN COMPOSABILITY (2:35-2:50)

**VISUAL:** Animated graphic on dark background.

1. User deposits USDC into PerpYield vault (arrow animation)

2. Vault mints SPL token shares (token with "PYIELD" label, mint address appears)

3. SPL token flows to 3 destinations simultaneously:
   - Kamino: "Lend shares for +2-5% extra yield"
   - Solend: "Use as collateral, up to 70% LTV"
   - Jupiter: "Swap shares for other tokens"

4. Arrow loops back: "Yield continues accruing to collateralized shares"

**VOICEOVER:**
> "Every deposit mints real SPL tokens. Not internal accounting, real on-chain shares. Lend them on Kamino for extra yield. Use as collateral on Solend. Swap on Jupiter. Your vault position is a composable Solana DeFi primitive."

**TEXT OVERLAY:** "Real SPL Tokens = Real DeFi Composability"

---

## SCENE 8: CLOSING (2:50-3:00)

**VISUAL:** Fast montage (0.5s per cut):
- Dashboard with PnL ticking up
- Marketplace with 4 vault cards
- AI advisor showing "TRENDING" regime
- Position table with "LIVE" indicator
- Backtest equity curve climbing
- SPL token composability graphic

Logo appears center screen.

**VOICEOVER:**
> "PerpYield. Automated delta-neutral yield on Pacifica. 75+ markets. AI-powered strategy selection. Real SPL token composability. Live testnet execution. The future of DeFi composability starts here."

**TEXT OVERLAYS** (sequential):
- "Auto-Execute | AI Advisor | SPL Shares"
- "Real Pacifica Testnet Execution"
- "DeFi Composability Track"

**FINAL FRAME:**
- PerpYield logo
- GitHub repo link
- "Built for Pacifica 2026 Hackathon"

**MUSIC:** Crescendo then clean outro

---

## PACIFICA API ENDPOINTS DEMONSTRATED

| Endpoint | Scene | Action |
|----------|-------|--------|
| `GET /info/prices` | 2, 4 | Live price feeds populating dashboard and AI advisor |
| `GET /funding_rate/history` | 4, 6 | Heatmap data, backtest equity curves |
| `GET /book` | 3 | Orderbook depth for position sizing |
| `GET /kline` | 4, 6 | AI volatility/trend analysis, backtesting |
| `GET /trades` | 2 | Trade confirmation on dashboard |
| `POST /orders/create_market` | 3 | Strategy engine opening positions |
| `POST /positions/tpsl` | 3 | Stop-loss/take-profit management |
| `WS subscribe_prices` | 2 | Real-time price updates on dashboard |
| `WS subscribe_orderbook` | 3 | Depth monitoring for execution |
| Builder Code | 3 | Fee capture integration |

## JUDGE CONCERN MATRIX

| Judge Concern | Addressed In | Timestamp |
|---------------|-------------|-----------|
| Product quality, polish | Dashboard, marketplace, risk filters | 0:20-0:50, 1:50-2:15 |
| Market fit, UX | Clone flow, deposit/withdraw, backtesting | 1:50-2:35 |
| Technical depth, real execution | Live positions, tx hashes, Ed25519 signing | 0:20-0:50, 0:50-1:20 |
| Innovation, AI | AI advisor, regime detection, confidence score | 1:20-1:50 |
| Pacifica integration | SDK calls, testnet positions, WebSocket, REST | 0:20-1:20, 2:35-2:50 |

## TECHNICAL REQUIREMENTS

| Item | Details |
|------|---------|
| Screen Recording | OBS Studio, 1920x1080, 30fps |
| Voiceover | Record separately, overlay in DaVinci Resolve |
| Background Music | Royalty-free upbeat electronic |
| Font | JetBrains Mono for data, Inter for headings |
| Color Grade | #0a0a0a bg, #00ff88 green, #ff4444 red |
| Cursor Effects | Subtle click ripple + cursor highlight in post |
| Zoom | 1.5x-2x zoom on APY counters, tx hashes, LIVE indicator |

## ALTERNATE CUTS

### 30-Second Twitter Version

| Time | Content |
|------|---------|
| 0-5 | Hook: "Funding rate farming, automated" |
| 5-15 | Dashboard + live positions + LIVE indicator |
| 15-22 | AI advisor regime detection + strategy switching |
| 22-27 | SPL composability graphic |
| 27-30 | Logo + "Built on Pacifica" + CTA |

### 60-Second Demo Day Version

| Time | Content |
|------|---------|
| 0-10 | Problem: manual funding farming is broken |
| 10-25 | Solution: dashboard + live positions + auto-rebalancing |
| 25-40 | AI advisor + strategy switching |
| 40-50 | Marketplace + clone + backtest |
| 50-60 | SPL composability + closing |

## KEY MESSAGING

When judges ask "Why PerpYield?", lead with these 5 differentiators:

1. **Auto-execution, not advisory** - Pacifica's AI Agent suggests trades but doesn't execute. PerpYield auto-trades 4 distinct strategies.
2. **Strategy switching without withdrawal** - Change strategies without exiting positions. First on Pacifica.
3. **1-click vault cloning** - Clone any vault config and customize. Unique across perps DEXs.
4. **Real SPL tokenized shares** - Not internal accounting like Hyperliquid. Real on-chain tokens composable across Solana DeFi.
5. **Pacifica-native execution** - Built for Pacifica's orderbook model, SDK, Ed25519 signing, WebSocket streams. Not a generic bot.

## PRE-RECORDING CHECKLIST

- [ ] Backend running at localhost:8000, all routes returning data
- [ ] Frontend running at localhost:3000, zero build errors
- [ ] Pacifica testnet wallet funded with USDC
- [ ] At least 2 active positions showing in position table
- [ ] Strategy engine running (green "Running" indicator)
- [ ] WebSocket connected (green "Connected" on dashboard)
- [ ] Marketplace showing all 4 vault cards with real APY data
- [ ] Backtest equity curve populated for at least 1 strategy
- [ ] AI advisor endpoint returning regime + recommendation
- [ ] Leaderboard page showing ranked vaults
- [ ] Clone flow tested end-to-end
- [ ] No empty states visible during recording
