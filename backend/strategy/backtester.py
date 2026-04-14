import math
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from pacifica.client import PacificaClient, sf
from strategy.funding_scanner import FundingScanner

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    initial_capital: float = 10_000.0
    min_funding_rate: float = 0.0001
    exit_funding_threshold: float = 0.00002
    leverage: float = 1.0
    taker_fee_pct: float = 0.05
    slippage_pct: float = 0.1
    max_positions: int = 3


@dataclass
class BacktestTrade:
    symbol: str
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    size: float
    side: str
    funding_collected: float
    fees_paid: float
    pnl: float


@dataclass
class BacktestResult:
    symbol: str
    period_start: int
    period_end: int
    initial_capital: float
    final_capital: float
    total_return_pct: float
    annualized_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    total_funding_collected: float
    total_fees_paid: float
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[BacktestTrade] = field(default_factory=list)


class Backtester:
    def __init__(self, client: PacificaClient, config: Optional[BacktestConfig] = None):
        self.client = client
        self.config = config or BacktestConfig()

    async def fetch_historical_data(
        self, symbol: str, days: int = 30
    ) -> tuple[list, list[dict]]:
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - (days * 24 * 3600 * 1000)

        candles = await self.client.get_klines(
            symbol=symbol,
            interval="1h",
            start_time=start_ms,
            end_time=now_ms,
        )

        all_funding = []
        cursor = None
        while True:
            resp = await self.client.get_market_funding_history(symbol, limit=4000, cursor=cursor)
            data = resp if isinstance(resp, dict) else {}
            records = data.get("data", [])
            all_funding.extend(records)
            if not data.get("has_more", False):
                break
            cursor = data.get("next_cursor")
            if not cursor:
                break

        funding_in_range = [f for f in all_funding if f.get("created_at", 0) >= start_ms]
        return candles, funding_in_range

    async def simulate(self, symbol: str, days: int = 30) -> BacktestResult:
        candles, funding_records = await self.fetch_historical_data(symbol, days)

        if not candles or not funding_records:
            raise ValueError(
                f"Insufficient data for {symbol}: {len(candles)} candles, "
                f"{len(funding_records)} funding records"
            )

        funding_map: dict[int, float] = {}
        for f in funding_records:
            hour_key = f.get("created_at", 0) // 3600000
            funding_map[hour_key] = sf(f.get("funding_rate"))

        capital = self.config.initial_capital
        equity_curve = []
        trades: list[BacktestTrade] = []
        daily_returns: list[float] = []
        peak_equity = capital
        max_drawdown = 0.0

        in_position = False
        entry_price = 0.0
        entry_time = 0
        position_size = 0.0
        position_funding = 0.0
        position_fees = 0.0
        prev_equity = capital

        for candle in candles:
            t = candle.timestamp
            hour_key = t // 3600000
            close_price = sf(candle.close)
            if close_price == 0:
                continue

            funding_rate = funding_map.get(hour_key, 0.0)

            if not in_position:
                if funding_rate >= self.config.min_funding_rate:
                    notional = capital * self.config.leverage
                    entry_fee = notional * (self.config.taker_fee_pct / 100)
                    slippage_cost = notional * (self.config.slippage_pct / 100)
                    total_entry_cost = entry_fee + slippage_cost

                    position_size = notional / close_price
                    entry_price = close_price
                    entry_time = t
                    position_funding = 0.0
                    position_fees = total_entry_cost
                    capital -= total_entry_cost
                    in_position = True
            else:
                notional = position_size * close_price
                funding_payment = notional * funding_rate
                position_funding += funding_payment
                capital += funding_payment

                should_exit = funding_rate < self.config.exit_funding_threshold

                if should_exit:
                    exit_fee = notional * (self.config.taker_fee_pct / 100)
                    exit_slippage = notional * (self.config.slippage_pct / 100)
                    total_exit_cost = exit_fee + exit_slippage

                    trade_pnl = position_funding - position_fees - total_exit_cost
                    capital -= total_exit_cost

                    trades.append(BacktestTrade(
                        symbol=symbol,
                        entry_time=entry_time,
                        exit_time=t,
                        entry_price=entry_price,
                        exit_price=close_price,
                        size=position_size,
                        side="short",
                        funding_collected=position_funding,
                        fees_paid=position_fees + total_exit_cost,
                        pnl=trade_pnl,
                    ))
                    in_position = False

            equity_curve.append({"timestamp": t, "equity": capital})

            if len(equity_curve) % 24 == 0 and prev_equity > 0:
                daily_ret = (capital - prev_equity) / prev_equity
                daily_returns.append(daily_ret)
                prev_equity = capital

            if capital > peak_equity:
                peak_equity = capital
            drawdown = (peak_equity - capital) / peak_equity * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        if in_position and candles:
            last_price = sf(candles[-1].close)
            if last_price > 0:
                notional = position_size * last_price
                exit_cost = notional * (self.config.taker_fee_pct / 100 + self.config.slippage_pct / 100)
                trade_pnl = position_funding - position_fees - exit_cost
                capital -= exit_cost
                trades.append(BacktestTrade(
                    symbol=symbol,
                    entry_time=entry_time,
                    exit_time=candles[-1].timestamp,
                    entry_price=entry_price,
                    exit_price=last_price,
                    size=position_size,
                    side="short",
                    funding_collected=position_funding,
                    fees_paid=position_fees + exit_cost,
                    pnl=trade_pnl,
                ))

        total_return_pct = ((capital - self.config.initial_capital) / self.config.initial_capital) * 100
        annualized = (total_return_pct / days * 365) if days > 0 else 0.0

        if len(daily_returns) > 1:
            mean_daily = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean_daily) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_daily = math.sqrt(variance) if variance > 0 else 0.001
            sharpe = (mean_daily / std_daily) * math.sqrt(365)
        else:
            sharpe = 0.0

        winning_trades = [t for t in trades if t.pnl > 0]
        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0.0
        total_funding = sum(t.funding_collected for t in trades)
        total_fees = sum(t.fees_paid for t in trades)

        period_start = candles[0].timestamp if candles else 0
        period_end = candles[-1].timestamp if candles else 0

        return BacktestResult(
            symbol=symbol,
            period_start=period_start,
            period_end=period_end,
            initial_capital=self.config.initial_capital,
            final_capital=capital,
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_drawdown,
            win_rate=win_rate,
            total_trades=len(trades),
            total_funding_collected=total_funding,
            total_fees_paid=total_fees,
            equity_curve=equity_curve,
            trades=trades,
        )

    async def run_multi_symbol(self, symbols: Optional[list[str]] = None, days: int = 30) -> dict:
        if symbols is None:
            scanner = FundingScanner(self.client)
            top = await scanner.get_top_opportunities(5)
            symbols = [o.symbol for o in top]

        results = {}
        for sym in symbols:
            try:
                result = await self.simulate(sym, days)
                results[sym] = {
                    "total_return": f"{result.total_return_pct:.2f}%",
                    "annualized_return": f"{result.annualized_return_pct:.2f}%",
                    "sharpe_ratio": f"{result.sharpe_ratio:.2f}",
                    "max_drawdown": f"{result.max_drawdown_pct:.2f}%",
                    "win_rate": f"{result.win_rate:.1f}%",
                    "total_trades": result.total_trades,
                    "funding_collected": f"${result.total_funding_collected:.2f}",
                    "fees_paid": f"${result.total_fees_paid:.2f}",
                }
                logger.info(f"Backtest {sym}: {result.total_return_pct:.2f}% return, Sharpe={result.sharpe_ratio:.2f}")
            except Exception as e:
                results[sym] = {"error": str(e)}
                logger.error(f"Backtest {sym} failed: {e}")

        return results

    def summary(self, result: BacktestResult) -> dict:
        return {
            "symbol": result.symbol,
            "period": f"{result.period_start} - {result.period_end}",
            "initial_capital": f"${result.initial_capital:,.2f}",
            "final_capital": f"${result.final_capital:,.2f}",
            "total_return": f"{result.total_return_pct:.2f}%",
            "annualized_return": f"{result.annualized_return_pct:.2f}%",
            "sharpe_ratio": f"{result.sharpe_ratio:.2f}",
            "max_drawdown": f"{result.max_drawdown_pct:.2f}%",
            "win_rate": f"{result.win_rate:.1f}%",
            "total_trades": result.total_trades,
            "total_funding_collected": f"${result.total_funding_collected:,.2f}",
            "total_fees_paid": f"${result.total_fees_paid:,.2f}",
            "net_funding": f"${result.total_funding_collected - result.total_fees_paid:,.2f}",
        }
