# PerpYield

**Automated Delta-Neutral Yield Vaults on Pacifica**

PerpYield is an automated yield farming vault that earns passive income from perpetual futures funding rates on Pacifica. Users deposit USDC, and the vault opens hedged delta-neutral positions that collect funding rate yield automatically. 

The platform features real-time analytics across 75+ markets, historical backtesting with equity curve analysis, and automated rebalancing to keep positions market-neutral at all times.

## Why This Matters

Funding rate farming is a proven DeFi strategy already used by sophisticated traders on venues like Hyperliquid and dYdX. PerpYield brings this strategy to Pacifica with one-click vault access, removing the complexity of manual position management. Instead of monitoring funding spreads, sizing hedges, and rebalancing by hand, users simply deposit into a vault and let the strategy engine handle execution, risk management, and yield collection.

## Track

**DeFi Composability** on the Pacifica Hackathon ($15K prize pool, deadline April 16, 2026)

## Architecture

```
+------------------------+          +---------------------------+          +----------------------------------+
|  Frontend              |          |  Backend API              |          |  Pacifica Testnet API            |
|  Next.js + Tailwind    |--------->|  FastAPI                  |--------->|  REST + WebSocket                |
|                        |          |                           |          |                                  |
|  - Dashboard           |          |  - Strategy Engine        |          |  - GET /info/prices              |
|  - Vault UI            |          |  - Funding Scanner        |          |  - GET /book                     |
|  - Analytics Heatmap   |          |  - Delta-Neutral Manager  |          |  - GET /kline                    |
|  - Backtesting Views   |          |  - Rebalancer             |          |  - GET /funding_rate/history     |
|  - OHLC Charts         |          |  - Vault Manager          |          |  - GET /trades                   |
|                        |          |  - Backtester             |          |  - POST /orders/create_market    |
|                        |          |                           |          |  - POST /orders/create           |
|                        |          |                           |          |  - POST /positions/tpsl          |
|                        |          |                           |          |  - WS subscribe_prices           |
|                        |          |                           |          |  - WS subscribe_orderbook        |
+------------------------+          +---------------------------+          +----------------------------------+
```

## Features

- **Real-time funding rate dashboard** across 75+ Pacifica markets with sortable rankings and annualized APY
- **Delta-neutral strategy engine** for market-direction agnostic yield collection
- **Automated position rebalancing** to maintain neutrality when exposure drifts
- **Historical funding rate analytics** with interactive heatmap visualization
- **Backtesting engine** with Sharpe ratio, max drawdown, win rate, and equity curve analysis
- **One-click vault deposit and withdraw** flows for simple user onboarding
- **Basis arbitrage opportunity scanner** to identify cross-market spreads
- **Builder Code integration** for Pacifica fee sharing

## Pacifica API Integration

PerpYield is built around deep integration with Pacifica's trading and market data APIs. This section details every endpoint used, which is critical for hackathon judging.

### REST Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /info/prices` | Fetch real-time funding rates and pricing for 75+ perpetual markets |
| `GET /book` | Orderbook depth for execution-aware position sizing |
| `GET /kline` | Historical OHLCV candles for backtesting and chart visualization |
| `GET /funding_rate/history` | Historical funding data for analytics heatmap and trend analysis |
| `GET /trades` | Recent trade activity for confirmation signals |
| `POST /orders/create_market` | Market orders for vault position entry and exit |
| `POST /orders/create` | Limit orders for capital-efficient execution |
| `POST /positions/tpsl` | Take-profit and stop-loss for position risk management |

### WebSocket Streams

| Stream | Purpose |
|--------|---------|
| `subscribe_prices` | Real-time price monitoring for live dashboard updates |
| `subscribe_orderbook` | Depth monitoring for execution quality |

### Builder Code

Builder Code integration for fee capture and Pacifica fee sharing revenue.

## How the Delta-Neutral Strategy Works

The delta-neutral strategy pairs offsetting long and short perpetual positions so the vault maintains close to zero net market exposure. Rather than betting on whether an asset price goes up or down, the strategy focuses on harvesting the funding rate imbalance between long and short traders.

When funding rates are positive (longs pay shorts), the vault takes the short side. When funding rates are negative (shorts pay longs), the vault takes the long side. In both cases, a matching hedge on the opposite side neutralizes price exposure, leaving only the funding payment as yield.

The system continuously monitors exposure drift, funding conditions, and orderbook depth, then rebalances positions when neutrality shifts beyond configurable thresholds or when a better opportunity appears on another market.

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, httpx, solders (Ed25519 Solana signing), numpy
- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, Recharts, Lucide icons
- **Exchange**: Pacifica perpetual futures (Solana), REST + WebSocket APIs
- **Signing**: Ed25519 via solders for authenticated order execution

## MCP Configuration

This project includes MCP (Model Context Protocol) integration for both Pacifica documentation and TradingView chart analysis:

### MCP Servers

| Server | Type | Purpose |
|--------|------|---------|
| `pacifica-docs` | Remote | Pacifica API documentation access |
| `tradingview` | Local | TradingView Desktop chart control via CDP |

### Configuration Files

- **`opencode.json`** - OpenCode configuration with MCP server and agent settings
- **`.cursor/mcp.json`** - Cursor-specific MCP configuration

### 1. Pacifica Docs MCP

Provides access to Pacifica API documentation:
- API documentation and endpoints
- Trading specifications and contract details
- Integration guides and examples

### 2. TradingView MCP

AI-assisted TradingView chart analysis. Connects Claude to your local TradingView Desktop app.

**Repository**: https://github.com/tradesdontlie/tradingview-mcp

**Prerequisites**:
- TradingView Desktop app with paid subscription
- Node.js 18+
- TradingView must be launched with `--remote-debugging-port=9222`

**Installed Tools** (68 MCP tools):
- Chart reading: `chart_get_state`, `quote_get`, `data_get_ohlcv`
- Pine Script development: `pine_set_source`, `pine_smart_compile`, `pine_get_errors`
- Chart control: `chart_set_symbol`, `chart_set_timeframe`, `chart_manage_indicator`
- Drawing: `draw_shape`, `draw_list`, `draw_clear`
- Alerts: `alert_create`, `alert_list`, `alert_delete`
- Replay mode: `replay_start`, `replay_step`, `replay_trade`
- Screenshots: `capture_screenshot`

**Quick Start**:
```bash
# 1. Launch TradingView with debug port (Mac)
./tradingview-mcp/scripts/launch_tv_debug_mac.sh

# 2. Or use the MCP tool
# "Use tv_launch to start TradingView in debug mode"

# 3. Verify connection
# "Use tv_health_check to verify TradingView is connected"
```

**CLI Commands**:
```bash
# All commands available as 'tv' CLI
cd tradingview-mcp
node src/cli/index.js status          # Check connection
node src/cli/index.js quote           # Get current price
node src/cli/index.js symbol AAPL     # Change symbol
node src/cli/index.js screenshot      # Capture chart
```

**Setup by Tool**:
- **OpenCode**: The `opencode.json` file contains both MCP configurations
- **Cursor**: Add to `.cursor/mcp.json`
- **Claude Desktop**: Add to `~/Library/Application Support/Claude/claude_desktop_config.json`

**Disclaimer**: Not affiliated with TradingView Inc. Requires valid TradingView subscription. All data processing occurs locally.

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 20+
- A Solana keypair (for authenticated operations on Pacifica testnet)

### Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your Pacifica testnet credentials
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Testnet Access

PerpYield connects to Pacifica testnet by default. Access the testnet app at https://test-app.pacifica.fi (code: "Pacifica") to get testnet USDC.

## Screenshots

| View | Path |
|------|------|
| Dashboard | `docs/screenshots/dashboard.png` |
| Analytics Heatmap | `docs/screenshots/analytics-heatmap.png` |
| Strategy Page | `docs/screenshots/strategy-page.png` |

## Backend API Endpoints

### Public (no auth required)

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/markets` | All market specifications |
| `GET /api/prices` | Real-time prices and funding rates |
| `GET /api/funding/rates` | Ranked funding rates with annualized APY |
| `GET /api/klines/{symbol}` | Historical OHLCV data |
| `GET /api/orderbook/{symbol}` | Live orderbook depth |
| `GET /api/strategies/funding` | Top funding rate opportunities |
| `GET /api/strategies/basis` | Basis arbitrage opportunities |
| `GET /api/backtest/{symbol}` | Run backtest simulation |
| `GET /api/scanner/summary` | Funding scanner summary |

### Authenticated (requires wallet signing)

| Endpoint | Description |
|----------|-------------|
| `POST /api/vault/deposit` | Deposit USDC into vault |
| `POST /api/vault/withdraw` | Withdraw from vault |
| `POST /api/strategy/start` | Start automated strategy |
| `POST /api/strategy/stop` | Stop automated strategy |
| `GET /api/positions` | View active positions |

## Project Structure

```
perpyield/
├── README.md
├── .gitignore
├── backend/
│   ├── .env.example
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── pacifica_client.py
│   ├── backtester.py
│   ├── vault_manager.py
│   ├── requirements.txt
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── funding_rate.py
│   │   └── basis_arb.py
│   └── strategy/
│       ├── __init__.py
│       ├── funding_scanner.py
│       ├── delta_neutral.py
│       ├── rebalancer.py
│       ├── vault_manager.py
│       └── backtester.py
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── tsconfig.json
    ├── postcss.config.mjs
    ├── eslint.config.mjs
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   ├── page.tsx
    │   │   └── globals.css
    │   ├── components/
    │   │   └── Header.tsx
    │   └── lib/
    │       └── api.ts
    └── public/
```

## Built for Pacifica Hackathon

Built for the Pacifica Hackathon, April 2026. Submitted under the **DeFi Composability** track as part of the $15K prize pool. Deadline: April 16, 2026.

## License

MIT
