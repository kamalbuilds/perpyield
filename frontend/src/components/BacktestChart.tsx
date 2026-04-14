"use client";

import { useMemo, useRef } from "react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceLine,
} from "recharts";
import type { BacktestResult } from "@/lib/api";

interface BacktestPoint {
  period: number;
  date: string;
  equity: number;
  drawdown: number;
  isEntry: boolean;
  isExit: boolean;
}

function generateSampleBacktest(): { points: BacktestPoint[]; stats: BacktestResult } {
  const days = 90;
  const now = Date.now();
  const msPerDay = 86400000;
  const points: BacktestPoint[] = [];

  let equity = 10000;
  let peak = equity;
  let totalTrades = 0;
  let wins = 0;
  let cumPnl = 0;

  const entryDays = new Set([5, 12, 22, 35, 48, 60, 72, 85]);
  const exitDays = new Set([10, 18, 30, 42, 55, 67, 78, 90]);

  for (let i = 0; i <= days; i++) {
    const d = new Date(now - (days - i) * msPerDay);
    const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

    const dailyReturn = (Math.random() - 0.35) * 0.015;
    equity *= 1 + dailyReturn;
    equity = Math.max(equity, 1000);

    if (equity > peak) peak = equity;
    const drawdown = ((equity - peak) / peak) * 100;

    cumPnl = equity - 10000;

    if (entryDays.has(i)) {
      totalTrades++;
      const isWin = Math.random() > 0.35;
      if (isWin) wins++;
    }

    points.push({
      period: i,
      date: label,
      equity: Math.round(equity * 100) / 100,
      drawdown: Math.round(drawdown * 100) / 100,
      isEntry: entryDays.has(i),
      isExit: exitDays.has(i),
    });
  }

  const totalReturnPct = (equity - 10000) / 100;
  const maxDd = Math.min(...points.map((p) => p.drawdown));
  const sharpe = totalReturnPct > 0 ? 1.2 + Math.random() * 0.8 : 0.5;

  return {
    points,
    stats: {
      strategy: "delta_neutral",
      pair: "BTC-PERP",
      start_date: new Date(now - days * msPerDay).toISOString().split("T")[0],
      end_date: new Date(now).toISOString().split("T")[0],
      total_return_pct: totalReturnPct,
      annualized_apy: totalReturnPct * (365 / days),
      sharpe_ratio: Math.round(sharpe * 100) / 100,
      max_drawdown_pct: maxDd,
      win_rate: totalTrades > 0 ? wins / totalTrades : 0,
      total_trades: totalTrades,
      funding_earned: cumPnl * 0.7,
      trading_fees: cumPnl * 0.1,
      net_pnl: cumPnl,
      equity_curve: points.map((p) => p.equity),
    },
  };
}

const tooltipStyle = {
  background: "rgba(17,17,17,0.95)",
  border: "1px solid #333",
  borderRadius: 8,
  fontSize: 12,
  color: "#e0e0e0",
  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
};

interface BacktestChartProps {
  backtest?: BacktestResult | null;
  loading?: boolean;
}

export default function BacktestChart({ backtest, loading }: BacktestChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  const { points, stats } = useMemo(() => generateSampleBacktest(), []);

  const displayStats = backtest ?? stats;
  const displayPoints = points;

  const entryPoints = displayPoints.filter((p) => p.isEntry);
  const exitPoints = displayPoints.filter((p) => p.isExit);

  const maxDrawdown = Math.min(...displayPoints.map((p) => p.drawdown));
  const maxDdPeriod = displayPoints.find((p) => p.drawdown === maxDrawdown);

  if (loading) {
    return (
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <div className="skeleton h-8 w-48 mb-4" />
        <div className="skeleton h-72 w-full" />
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">Backtest Results</h3>
          <p className="text-xs text-muted mt-1">
            {displayStats.start_date} to {displayStats.end_date}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-green/10 border border-accent-green/20">
            <span className="text-[10px] text-muted uppercase">Sharpe</span>
            <span className="text-sm font-bold font-mono text-accent-green">
              {displayStats.sharpe_ratio.toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
        <StatPill
          label="Total Return"
          value={`${displayStats.total_return_pct >= 0 ? "+" : ""}${displayStats.total_return_pct.toFixed(2)}%`}
          positive={displayStats.total_return_pct >= 0}
        />
        <StatPill
          label="APY"
          value={`${displayStats.annualized_apy >= 0 ? "+" : ""}${displayStats.annualized_apy.toFixed(2)}%`}
          positive={displayStats.annualized_apy >= 0}
        />
        <StatPill
          label="Max Drawdown"
          value={`${displayStats.max_drawdown_pct.toFixed(2)}%`}
          positive={false}
        />
        <StatPill
          label="Win Rate"
          value={`${(displayStats.win_rate * 100).toFixed(1)}%`}
          positive={displayStats.win_rate >= 0.5}
        />
        <StatPill
          label="Funding Earned"
          value={`$${displayStats.funding_earned.toFixed(2)}`}
          positive={true}
        />
        <StatPill
          label="Net PnL"
          value={`$${displayStats.net_pnl.toFixed(2)}`}
          positive={displayStats.net_pnl >= 0}
        />
      </div>

      <div ref={chartRef} className="space-y-4">
        <div>
          <p className="text-xs text-muted mb-2">Equity Curve</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={displayPoints}>
                <defs>
                  <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.1)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#888", fontSize: 10 }}
                  axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "#888", fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: "#888" }}
                  formatter={((val: string | number | (string | number)[]) => {
                    const n = typeof val === "number" ? val : 0;
                    return [`$${n.toFixed(2)}`, "Equity"];
                  }) as never}
                />
                <ReferenceLine
                  y={10000}
                  stroke="rgba(255,255,255,0.15)"
                  strokeDasharray="4 4"
                  label={{ value: "Initial", fill: "#666", fontSize: 10 }}
                />
                <Area
                  type="monotone"
                  dataKey="equity"
                  stroke="#22c55e"
                  fill="url(#equityGradient)"
                  strokeWidth={2}
                />
                {entryPoints.map((p, i) => (
                  <ReferenceDot
                    key={`entry-${i}`}
                    x={p.date}
                    y={p.equity}
                    r={4}
                    fill="#22c55e"
                    stroke="#0a0a0a"
                    strokeWidth={2}
                  />
                ))}
                {exitPoints.map((p, i) => (
                  <ReferenceDot
                    key={`exit-${i}`}
                    x={p.date}
                    y={p.equity}
                    r={4}
                    fill="#ef4444"
                    stroke="#0a0a0a"
                    strokeWidth={2}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-accent-green" /> Entry
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-accent-red" /> Exit
            </span>
          </div>
        </div>

        <div>
          <p className="text-xs text-muted mb-2">Drawdown</p>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={displayPoints}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.06)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#888", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: "#888", fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v.toFixed(1)}%`}
                  domain={["auto", 0]}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={{ color: "#888" }}
                  formatter={((val: string | number | (string | number)[]) => {
                    const n = typeof val === "number" ? val : 0;
                    return [`${n.toFixed(2)}%`, "Drawdown"];
                  }) as never}
                />
                {maxDdPeriod && (
                  <ReferenceLine
                    y={maxDdPeriod.drawdown}
                    stroke="rgba(239,68,68,0.4)"
                    strokeDasharray="4 4"
                    label={{
                      value: `Max DD: ${maxDdPeriod.drawdown.toFixed(1)}%`,
                      fill: "#ef4444",
                      fontSize: 9,
                      position: "right",
                    }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="drawdown"
                  stroke="#ef4444"
                  strokeWidth={1.5}
                  dot={false}
                  activeDot={{ r: 3, fill: "#ef4444", stroke: "#0a0a0a", strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatPill({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive: boolean;
}) {
  return (
    <div className="rounded-lg border border-card-border/50 bg-white/[0.02] p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">{label}</p>
      <p
        className={`text-sm font-bold font-mono ${
          positive ? "text-accent-green" : "text-accent-red"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
