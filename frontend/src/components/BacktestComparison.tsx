"use client";

import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
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

interface BacktestComparisonProps {
  results: StrategyBacktestResponse[];
}

export default function BacktestComparison({ results }: BacktestComparisonProps) {
  if (results.length < 2) return null;

  const maxLen = Math.max(...results.map((r) => r.equity_curve_sample?.length ?? 0));
  const chartData = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, number> = { index: i };
    results.forEach((r) => {
      const curve = r.equity_curve_sample ?? [];
      const curvePoint = curve[i] ?? curve[curve.length - 1];
      point[r.strategy_id] = curvePoint?.equity ?? 0;
    });
    return point;
  });

  const metrics = [
    { key: "total_return_pct", label: "Total Return", suffix: "%", decimals: 2 },
    { key: "annualized_apy", label: "APY", suffix: "%", decimals: 2 },
    { key: "sharpe_ratio", label: "Sharpe", suffix: "", decimals: 2 },
    { key: "max_drawdown_pct", label: "Max DD", suffix: "%", decimals: 2 },
    { key: "win_rate", label: "Win Rate", suffix: "%", decimals: 1 },
    { key: "total_trades", label: "Trades", suffix: "", decimals: 0 },
  ] as const;

  function getWinner(metricKey: string): number {
    const isLowerBetter = metricKey === "max_drawdown_pct";
    let bestIdx = 0;
    let bestVal = results[0].backtest[metricKey as keyof typeof results[0]["backtest"]] as number;
    for (let i = 1; i < results.length; i++) {
      const val = results[i].backtest[metricKey as keyof typeof results[0]["backtest"]] as number;
      if (isLowerBetter ? val < bestVal : val > bestVal) {
        bestVal = val;
        bestIdx = i;
      }
    }
    return bestIdx;
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-bold">Strategy Comparison</h3>
        <span className="text-xs text-muted">{results.length} strategies</span>
      </div>

      <div className="rounded-lg border border-card-border bg-card-bg p-4">
        <h4 className="text-xs text-muted uppercase tracking-wider mb-3 font-medium">Equity Curves</h4>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
              <defs>
                {results.map((r) => (
                  <linearGradient key={r.strategy_id} id={`cmp-gradient-${r.strategy_id}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={STRATEGY_COLORS[r.strategy_id] ?? "#888"} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={STRATEGY_COLORS[r.strategy_id] ?? "#888"} stopOpacity={0} />
                  </linearGradient>
                ))}
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
                formatter={((value: string | number | (string | number)[], name: string) => {
                  const n = typeof value === "number" ? value : 0;
                  return [`$${n.toFixed(2)}`, STRATEGY_NAMES[name] ?? name];
                }) as never}
              />
              <Legend
                formatter={(value: string) => (
                  <span style={{ color: STRATEGY_COLORS[value] ?? "#888", fontSize: "12px" }}>
                    {STRATEGY_NAMES[value] ?? value}
                  </span>
                )}
              />
              {results.map((r) => {
                const c = STRATEGY_COLORS[r.strategy_id] ?? "#888";
                return (
                  <Area
                    key={r.strategy_id}
                    type="monotone"
                    dataKey={r.strategy_id}
                    name={r.strategy_id}
                    stroke={c}
                    strokeWidth={2}
                    fill={`url(#cmp-gradient-${r.strategy_id})`}
                    dot={false}
                    activeDot={{ r: 3, fill: c, stroke: "#0a0a0a", strokeWidth: 2 }}
                  />
                );
              })}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-lg border border-card-border bg-card-bg overflow-hidden">
        <div className="px-4 py-3 border-b border-card-border">
          <h4 className="text-xs text-muted uppercase tracking-wider font-medium">Metrics Comparison</h4>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-card-border text-xs text-muted uppercase tracking-wider">
                <th className="text-left px-4 py-3">Metric</th>
                {results.map((r) => (
                  <th key={r.strategy_id} className="text-right px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <span
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ backgroundColor: STRATEGY_COLORS[r.strategy_id] ?? "#888" }}
                      />
                      {STRATEGY_NAMES[r.strategy_id] ?? r.strategy_id}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => {
                const winnerIdx = getWinner(m.key);
                return (
                  <tr key={m.key} className="border-b border-card-border/40 hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-2.5 text-xs text-muted font-medium">{m.label}</td>
                    {results.map((r, i) => {
                      const val = r.backtest[m.key as keyof typeof r.backtest] as number;
                      const isWinner = i === winnerIdx;
                      const color = STRATEGY_COLORS[r.strategy_id] ?? "#888";
                      return (
                        <td key={r.strategy_id} className="px-4 py-2.5 text-right font-mono text-xs relative">
                          {isWinner && (
                            <span
                              className="absolute -left-1 top-1/2 -translate-y-1/2 text-[9px] px-1 py-0.5 rounded font-bold"
                              style={{ backgroundColor: color + "20", color }}
                            >
                              WIN
                            </span>
                          )}
                          <span className={isWinner ? "font-bold" : ""}>
                            {m.key === "total_return_pct" || m.key === "annualized_apy"
                              ? (val >= 0 ? "+" : "")
                              : ""}
                            {val.toFixed(m.decimals)}{m.suffix}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
