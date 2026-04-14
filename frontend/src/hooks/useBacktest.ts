"use client";

import { useState, useCallback, useRef } from "react";
import {
  fetchStrategyBacktest,
  type StrategyBacktestRequest,
  type StrategyBacktestResponse,
} from "@/lib/api";

export interface BacktestCacheEntry {
  key: string;
  result: StrategyBacktestResponse;
  timestamp: number;
}

const CACHE_TTL = 5 * 60 * 1000;

function makeCacheKey(req: StrategyBacktestRequest): string {
  return `${req.strategy_id}_${req.symbol}_${req.days}_${JSON.stringify(req.config ?? {})}`;
}

export function useBacktest() {
  const [results, setResults] = useState<StrategyBacktestResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cacheRef = useRef<Map<string, BacktestCacheEntry>>(new Map());

  const runBacktest = useCallback(async (req: StrategyBacktestRequest) => {
    const key = makeCacheKey(req);
    const cached = cacheRef.current.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      setResults((prev) => {
        const filtered = prev.filter((r) => !(r.strategy_id === cached.result.strategy_id && r.symbol === cached.result.symbol && r.days === cached.result.days));
        return [...filtered, cached.result];
      });
      return cached.result;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await fetchStrategyBacktest(req);
      cacheRef.current.set(key, { key, result, timestamp: Date.now() });
      setResults((prev) => {
        const filtered = prev.filter((r) => !(r.strategy_id === result.strategy_id && r.symbol === result.symbol && r.days === result.days));
        return [...filtered, result];
      });
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Backtest failed";
      setError(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearResults = useCallback(() => {
    setResults([]);
    setError(null);
  }, []);

  const removeResult = useCallback((strategyId: string, symbol: string) => {
    setResults((prev) => prev.filter((r) => !(r.strategy_id === strategyId && r.symbol === symbol)));
  }, []);

  const exportJSON = useCallback(() => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backtest-results-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  const exportCSV = useCallback(() => {
    if (results.length === 0) return;
    const headers = ["Strategy", "Symbol", "Days", "Total Return %", "APY %", "Sharpe", "Max Drawdown %", "Win Rate %", "Total Trades", "Funding Earned", "Fees", "Net PnL"];
    const rows = results.map((r) => [
      r.strategy_id,
      r.symbol,
      r.days,
      r.backtest.total_return_pct,
      r.backtest.annualized_apy,
      r.backtest.sharpe_ratio,
      r.backtest.max_drawdown_pct,
      r.backtest.win_rate,
      r.backtest.total_trades,
      r.backtest.funding_earned,
      r.backtest.trading_fees,
      r.backtest.net_pnl,
    ]);
    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backtest-results-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [results]);

  return {
    results,
    loading,
    error,
    runBacktest,
    clearResults,
    removeResult,
    exportJSON,
    exportCSV,
  };
}
