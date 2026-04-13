"use client";

import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import {
  fetchFundingRates,
  fetchFundingHistory,
  fetchBacktest,
  type FundingRateEntry,
  type FundingHistory,
  type BacktestResult,
} from "@/lib/api";

function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton ${className ?? ""}`} />;
}

export default function AnalyticsPage() {
  const [rates, setRates] = useState<FundingRateEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // History chart state
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [history, setHistory] = useState<FundingHistory | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Backtest state
  const [backtestSymbol, setBacktestSymbol] = useState<string>("");
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(
    null
  );
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchFundingRates();
        setRates(data);
        if (data.length > 0) {
          setSelectedSymbol(data[0].symbol);
          setBacktestSymbol(data[0].symbol);
        }
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load rates");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Load funding history when symbol changes
  useEffect(() => {
    if (!selectedSymbol) return;
    setHistoryLoading(true);
    fetchFundingHistory(selectedSymbol)
      .then((data) => setHistory(data))
      .catch(() => setHistory(null))
      .finally(() => setHistoryLoading(false));
  }, [selectedSymbol]);

  const sortedRates = [...rates].sort(
    (a, b) => Math.abs(b.annualized_apy) - Math.abs(a.annualized_apy)
  );

  async function runBacktest() {
    if (!backtestSymbol) return;
    setBacktestLoading(true);
    setBacktestError(null);
    setBacktestResult(null);
    try {
      const result = await fetchBacktest(backtestSymbol, 30);
      setBacktestResult(result);
    } catch (e) {
      setBacktestError(
        e instanceof Error ? e.message : "Backtest failed"
      );
    } finally {
      setBacktestLoading(false);
    }
  }

  // Prepare history chart data
  const historyChartData = (history?.rates ?? []).map((r) => ({
    time: new Date(r.timestamp * 1000).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
    }),
    rate: r.rate * 100,
    apy: r.rate * 100 * 3 * 365,
  }));

  // Prepare equity curve chart data
  const equityCurveData = (backtestResult?.equity_curve ?? []).map(
    (val, idx) => ({
      period: idx,
      value: val,
    })
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Analytics</h2>
        <p className="text-sm text-muted mt-1">
          Funding rate analytics, historical data, and backtesting
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red">
          {error}
        </div>
      )}

      {/* Funding Rate Heatmap */}
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <h3 className="text-sm font-semibold mb-4">Funding Rate Heatmap</h3>
        {loading ? (
          <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
            {Array.from({ length: 16 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : sortedRates.length === 0 ? (
          <p className="text-sm text-muted py-4">
            No data available. Ensure backend is running at localhost:8000.
          </p>
        ) : (
          <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-7 xl:grid-cols-9 gap-2">
            {sortedRates.slice(0, 36).map((r) => {
              const isPositive = r.funding_rate >= 0;
              const absApy = Math.abs(r.annualized_apy);
              const intensity = Math.min(absApy / 500, 1);
              const bg = isPositive
                ? `rgba(0, 255, 136, ${0.08 + intensity * 0.35})`
                : `rgba(255, 68, 68, ${0.08 + intensity * 0.35})`;
              return (
                <div
                  key={r.symbol}
                  className="p-2.5 rounded-lg cursor-default border border-white/5 hover:border-white/15 transition-colors"
                  style={{ background: bg }}
                  title={`${r.symbol}: ${r.annualized_apy.toFixed(2)}% APY`}
                >
                  <p className="text-xs font-semibold text-white/90 truncate">{r.symbol}</p>
                  <p
                    className={`text-base font-mono font-bold ${
                      isPositive ? "text-accent-green" : "text-accent-red"
                    }`}
                  >
                    {isPositive ? "+" : ""}
                    {absApy >= 1000 ? `${(absApy / 1000).toFixed(1)}k` : r.annualized_apy.toFixed(1)}%
                  </p>
                  <p className="text-[10px] text-white/50">APY</p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Historical Funding Chart */}
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">Historical Funding Rate</h3>
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-white/5 border border-card-border rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-accent-green/50 transition-colors"
          >
            {rates.map((r) => (
              <option key={r.symbol} value={r.symbol} className="bg-[#111]">
                {r.symbol}
              </option>
            ))}
          </select>
        </div>

        {historyLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : historyChartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted">
            No historical data available for {selectedSymbol}
          </div>
        ) : (
          <>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={historyChartData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#222"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="time"
                    tick={{ fill: "#888", fontSize: 11 }}
                    axisLine={{ stroke: "#222" }}
                    tickLine={false}
                  />
                  <YAxis
                    yAxisId="rate"
                    tick={{ fill: "#888", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(3)}%`}
                  />
                  <YAxis
                    yAxisId="apy"
                    orientation="right"
                    tick={{ fill: "#888", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v: number) => `${v.toFixed(0)}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#111",
                      border: "1px solid #222",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "#888" }}
                  />
                  <Line
                    yAxisId="rate"
                    type="monotone"
                    dataKey="rate"
                    stroke="#00ff88"
                    strokeWidth={1.5}
                    dot={false}
                    name="Funding Rate %"
                  />
                  <Line
                    yAxisId="apy"
                    type="monotone"
                    dataKey="apy"
                    stroke="#4488ff"
                    strokeWidth={1.5}
                    dot={false}
                    name="Annualized APY %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {history && (
              <div className="flex gap-6 mt-3 text-xs text-muted">
                <span>
                  Avg 24h:{" "}
                  <span className="text-foreground font-mono">
                    {(history.avg_rate_24h * 100).toFixed(4)}%
                  </span>
                </span>
                <span>
                  Avg 7d:{" "}
                  <span className="text-foreground font-mono">
                    {(history.avg_rate_7d * 100).toFixed(4)}%
                  </span>
                </span>
                <span>
                  Positive rate:{" "}
                  <span className="text-foreground font-mono">
                    {history.positive_rate_pct.toFixed(1)}%
                  </span>
                </span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Backtest */}
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <h3 className="text-sm font-semibold mb-4">Backtest Results</h3>
        <div className="flex items-center gap-3 mb-4">
          <select
            value={backtestSymbol}
            onChange={(e) => setBacktestSymbol(e.target.value)}
            className="bg-white/5 border border-card-border rounded-lg px-3 py-1.5 text-sm font-mono focus:outline-none focus:border-accent-green/50 transition-colors"
          >
            {rates.map((r) => (
              <option key={r.symbol} value={r.symbol} className="bg-[#111]">
                {r.symbol}
              </option>
            ))}
          </select>
          <button
            onClick={runBacktest}
            disabled={backtestLoading || !backtestSymbol}
            className="px-4 py-1.5 rounded-lg text-sm font-medium bg-accent-green text-black hover:bg-accent-green/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {backtestLoading ? "Running..." : "Run Backtest"}
          </button>
        </div>

        {backtestError && (
          <div className="p-3 rounded-lg border border-accent-red/30 bg-accent-red/5 text-sm text-accent-red mb-4">
            {backtestError}
          </div>
        )}

        {backtestLoading && (
          <div className="space-y-3">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        )}

        {backtestResult && !backtestLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <BacktestStat
                label="Total Return"
                value={`${backtestResult.total_return_pct.toFixed(2)}%`}
                positive={backtestResult.total_return_pct >= 0}
              />
              <BacktestStat
                label="APY"
                value={`${backtestResult.annualized_apy.toFixed(2)}%`}
                positive={backtestResult.annualized_apy >= 0}
              />
              <BacktestStat
                label="Sharpe Ratio"
                value={backtestResult.sharpe_ratio.toFixed(2)}
                positive={backtestResult.sharpe_ratio >= 1}
              />
              <BacktestStat
                label="Max Drawdown"
                value={`${backtestResult.max_drawdown_pct.toFixed(2)}%`}
                positive={false}
              />
              <BacktestStat
                label="Win Rate"
                value={`${(backtestResult.win_rate * 100).toFixed(1)}%`}
                positive={backtestResult.win_rate >= 0.5}
              />
              <BacktestStat
                label="Total Trades"
                value={`${backtestResult.total_trades}`}
              />
            </div>

            {equityCurveData.length > 0 && (
              <div className="h-56">
                <p className="text-xs text-muted mb-2">Equity Curve</p>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={equityCurveData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#222"
                      vertical={false}
                    />
                    <XAxis
                      dataKey="period"
                      tick={{ fill: "#888", fontSize: 10 }}
                      axisLine={{ stroke: "#222" }}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: "#888", fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(v: number) =>
                        `$${(v / 1000).toFixed(1)}k`
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#111",
                        border: "1px solid #222",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(val) => {
                        const n = typeof val === "number" ? val : 0;
                        return [`$${n.toFixed(2)}`, "Portfolio Value"];
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="#00ff88"
                      fill="rgba(0,255,136,0.08)"
                      strokeWidth={1.5}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {!backtestResult && !backtestLoading && !backtestError && (
          <div className="py-8 text-center text-sm text-muted">
            Select a symbol and click &quot;Run Backtest&quot; to see results
          </div>
        )}
      </div>
    </div>
  );
}

function BacktestStat({
  label,
  value,
  positive,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  const color =
    positive === undefined
      ? "text-foreground"
      : positive
      ? "text-accent-green"
      : "text-accent-red";
  return (
    <div className="rounded-lg border border-card-border/50 bg-white/[0.02] p-3">
      <p className="text-[10px] text-muted uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className={`text-lg font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}
