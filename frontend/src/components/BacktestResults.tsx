"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { StrategyBacktestResponse } from "@/lib/api";

const STRATEGY_NAMES: Record<string, string> = {
  delta_neutral: "Delta Neutral",
  momentum_swing: "Momentum Swing",
  mean_reversion: "Mean Reversion",
  volatility_breakout: "Volatility Breakout",
};

const STRATEGY_COLORS: Record<string, string> = {
  delta_neutral: "#00ff88",
  momentum_swing: "#4488ff",
  mean_reversion: "#a855f7",
  volatility_breakout: "#ff8800",
};

interface SummaryCardProps {
  label: string;
  value: string;
  accent?: "green" | "red" | "blue" | "purple";
  index: number;
}

function SummaryCard({ label, value, accent, index }: SummaryCardProps) {
  const valueColor =
    accent === "green" ? "text-accent-green"
    : accent === "red" ? "text-accent-red"
    : accent === "blue" ? "text-blue-400"
    : accent === "purple" ? "text-purple-400"
    : "text-foreground";

  const borderColor =
    accent === "green" ? "border-accent-green/20"
    : accent === "red" ? "border-accent-red/20"
    : accent === "blue" ? "border-blue-500/20"
    : accent === "purple" ? "border-purple-500/20"
    : "border-card-border";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.4 }}
      className={`rounded-lg border bg-card-bg p-4 ${borderColor}`}
    >
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1.5">{label}</p>
      <p className={`text-xl font-bold tracking-tight font-mono ${valueColor}`}>{value}</p>
    </motion.div>
  );
}

interface BacktestResultsProps {
  result: StrategyBacktestResponse;
  onSave?: () => void;
  onCompare?: () => void;
}

export default function BacktestResults({ result, onSave, onCompare }: BacktestResultsProps) {
  const [showTrades, setShowTrades] = useState(false);
  const bt = result.backtest;
  const color = STRATEGY_COLORS[result.strategy_id] ?? "#00ff88";

  const isPositiveReturn = bt.total_return_pct >= 0;
  const isPositivePnl = bt.net_pnl >= 0;

  const equityData = (result.equity_curve_sample ?? []).map((v, i) => ({
    index: i,
    equity: v.equity ?? 0,
  }));

  const summaryCards: { label: string; value: string; accent?: "green" | "red" | "blue" | "purple" }[] = [
    { label: "Total Return", value: `${isPositiveReturn ? "+" : ""}${bt.total_return_pct.toFixed(2)}%`, accent: isPositiveReturn ? "green" : "red" },
    { label: "Annualized APY", value: `${bt.annualized_apy.toFixed(2)}%`, accent: bt.annualized_apy >= 0 ? "green" : "red" },
    { label: "Sharpe Ratio", value: bt.sharpe_ratio.toFixed(2), accent: bt.sharpe_ratio >= 1 ? "green" : bt.sharpe_ratio >= 0 ? "blue" : "red" },
    { label: "Max Drawdown", value: `${bt.max_drawdown_pct.toFixed(2)}%`, accent: "red" },
    { label: "Win Rate", value: `${bt.win_rate.toFixed(1)}%`, accent: bt.win_rate >= 50 ? "green" : "red" },
    { label: "Net PnL", value: `${isPositivePnl ? "+" : ""}$${bt.net_pnl.toFixed(2)}`, accent: isPositivePnl ? "green" : "red" },
  ];

  const monthlyReturns = (() => {
    const curve = result.equity_curve_sample ?? [];
    if (curve.length < 2) return [];
    const step = Math.max(1, Math.floor(curve.length / result.days));
    const months: { month: string; return_pct: number }[] = [];
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let prev = curve[0].equity ?? 0;
    const startIdx = Math.floor(step * 0);
    for (let i = startIdx + step; i < curve.length; i += step) {
      const curr = curve[i].equity ?? 0;
      const ret = prev !== 0 ? ((curr - prev) / Math.abs(prev)) * 100 : 0;
      const mIdx = months.length % 12;
      months.push({ month: monthNames[mIdx], return_pct: ret });
      prev = curr;
      if (months.length >= 6) break;
    }
    return months;
  })();

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: color }}
          />
          <h3 className="text-base font-bold">
            {STRATEGY_NAMES[result.strategy_id] ?? result.strategy_id}
            <span className="text-muted font-normal ml-2 text-sm">
              {result.symbol} / {result.days}d
            </span>
          </h3>
        </div>
        <div className="flex gap-2">
          {onSave && (
            <button
              onClick={onSave}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
            >
              Save
            </button>
          )}
          {onCompare && (
            <button
              onClick={onCompare}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-accent-green/30 bg-accent-green/5 text-accent-green hover:bg-accent-green/10 transition-colors"
            >
              Compare
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {summaryCards.map((card, i) => (
          <SummaryCard key={card.label} label={card.label} value={card.value} accent={card.accent} index={i} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-lg border border-card-border bg-card-bg p-4">
          <h4 className="text-xs text-muted uppercase tracking-wider mb-3 font-medium">Equity Curve</h4>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                <defs>
                  <linearGradient id={`gradient-${result.strategy_id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#222" />
                <XAxis
                  dataKey="index"
                  tick={{ fontSize: 10, fill: "#888" }}
                  axisLine={{ stroke: "#333" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#888" }}
                  axisLine={{ stroke: "#333" }}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}K`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1a1a1a",
                    border: "1px solid #333",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#e0e0e0",
                  }}
                  formatter={((value: string | number | (string | number)[]) => {
                    const n = typeof value === "number" ? value : 0;
                    return [`$${n.toFixed(2)}`, "Equity"];
                  }) as never}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke={color}
                  strokeWidth={2}
                  fill={`url(#gradient-${result.strategy_id})`}
                  dot={false}
                  activeDot={{ r: 4, fill: color, stroke: "#0a0a0a", strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-lg border border-card-border bg-card-bg p-4">
          <h4 className="text-xs text-muted uppercase tracking-wider mb-3 font-medium">Monthly Returns</h4>
          <div className="space-y-2">
            {monthlyReturns.length === 0 ? (
              <p className="text-xs text-muted text-center py-4">Insufficient data for monthly breakdown</p>
            ) : (
              monthlyReturns.map((m, i) => (
                <motion.div
                  key={m.month}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.05 }}
                  className="flex items-center justify-between"
                >
                  <span className="text-xs text-muted">{m.month}</span>
                  <div className="flex items-center gap-2 flex-1 mx-3">
                    <div className="h-2 rounded-full bg-white/5 flex-1 overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${Math.min(Math.abs(m.return_pct), 100)}%` }}
                        transition={{ delay: 0.5 + i * 0.05, duration: 0.5 }}
                        className={`h-full rounded-full ${m.return_pct >= 0 ? "bg-accent-green/60" : "bg-accent-red/60"}`}
                        style={{ marginLeft: m.return_pct < 0 ? "auto" : 0 }}
                      />
                    </div>
                  </div>
                  <span className={`text-xs font-mono font-medium ${m.return_pct >= 0 ? "text-accent-green" : "text-accent-red"}`}>
                    {m.return_pct >= 0 ? "+" : ""}{m.return_pct.toFixed(2)}%
                  </span>
                </motion.div>
              ))
            )}
          </div>

          <div className="mt-4 pt-3 border-t border-card-border space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-muted">Total Trades</span>
              <span className="font-mono font-medium">{bt.total_trades}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted">Funding Earned</span>
              <span className="font-mono font-medium text-accent-green">${bt.funding_earned.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted">Trading Fees</span>
              <span className="font-mono font-medium text-accent-red">${bt.trading_fees.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      <div>
        <button
          onClick={() => setShowTrades(!showTrades)}
          className="flex items-center gap-2 text-xs text-muted hover:text-foreground transition-colors"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            className={`transition-transform ${showTrades ? "rotate-90" : ""}`}
          >
            <path d="M6 4l4 4-4 4" stroke="currentColor" strokeWidth="2" fill="none" />
          </svg>
          Trade History ({bt.total_trades} trades)
        </button>

        {showTrades && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="mt-2"
          >
            <div className="rounded-lg border border-card-border bg-card-bg p-4 text-sm text-muted text-center">
              Detailed trade history available via API. Run <code className="px-1.5 py-0.5 rounded bg-white/5 font-mono text-xs">GET /api/strategies/{result.strategy_id}/backtest</code> for full breakdown.
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
