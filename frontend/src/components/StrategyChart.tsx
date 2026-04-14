"use client";

import { useState, useMemo, useRef, useCallback } from "react";
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
  Legend,
} from "recharts";
import type { VaultStatus } from "@/lib/api";

type TimeRange = "1D" | "1W" | "1M" | "3M" | "ALL";

interface TimeSeriesPoint {
  date: string;
  value: number;
  sharePrice: number;
  deposits: number;
}

function generateSampleData(range: TimeRange): TimeSeriesPoint[] {
  const points: TimeSeriesPoint[] = [];
  const now = Date.now();
  const msPerHour = 3600000;
  let count: number;
  let intervalMs: number;

  switch (range) {
    case "1D":
      count = 24;
      intervalMs = msPerHour;
      break;
    case "1W":
      count = 7 * 4;
      intervalMs = msPerHour * 6;
      break;
    case "1M":
      count = 30;
      intervalMs = msPerHour * 24;
      break;
    case "3M":
      count = 90;
      intervalMs = msPerHour * 24;
      break;
    case "ALL":
      count = 365;
      intervalMs = msPerHour * 24;
      break;
  }

  let value = 10000;
  let deposits = 10000;
  let sharePrice = 1.0;

  for (let i = 0; i < count; i++) {
    const ts = now - (count - i) * intervalMs;
    const d = new Date(ts);
    const label =
      range === "1D"
        ? d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
        : range === "1W"
        ? d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit" })
        : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

    const fundingYield = (Math.random() - 0.35) * 30;
    value += fundingYield;
    sharePrice = value / deposits;

    if (i === Math.floor(count * 0.3)) {
      deposits += 5000;
      value += 5000;
    }
    if (i === Math.floor(count * 0.7)) {
      deposits += 3000;
      value += 3000;
    }

    points.push({
      date: label,
      value: Math.round(value * 100) / 100,
      sharePrice: Math.round(sharePrice * 10000) / 10000,
      deposits: Math.round(deposits * 100) / 100,
    });
  }
  return points;
}

interface StrategyChartProps {
  vault?: VaultStatus | null;
  loading?: boolean;
}

function ChartExportButton({
  chartRef,
  filename,
}: {
  chartRef: React.RefObject<HTMLDivElement | null>;
  filename: string;
}) {
  const handleExport = useCallback(() => {
    const el = chartRef.current;
    if (!el) return;
    const svg = el.querySelector("svg");
    if (!svg) return;
    const svgData = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = new Image();
    img.onload = () => {
      canvas.width = img.width * 2;
      canvas.height = img.height * 2;
      ctx.scale(2, 2);
      ctx.fillStyle = "#0a0a0a";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      const a = document.createElement("a");
      a.download = filename;
      a.href = canvas.toDataURL("image/png");
      a.click();
    };
    img.src = "data:image/svg+xml;base64," + btoa(unescape(encodeURIComponent(svgData)));
  }, [chartRef, filename]);

  return (
    <button
      onClick={handleExport}
      className="px-3 py-1 rounded-md text-xs font-medium border border-card-border bg-white/5 text-muted hover:text-foreground hover:border-accent-green/30 transition-colors"
    >
      Export PNG
    </button>
  );
}

const tooltipStyle = {
  background: "rgba(17,17,17,0.95)",
  border: "1px solid #333",
  borderRadius: 8,
  fontSize: 12,
  color: "#e0e0e0",
  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
};

const rangeOptions: TimeRange[] = ["1D", "1W", "1M", "3M", "ALL"];

export default function StrategyChart({ vault, loading }: StrategyChartProps) {
  const [range, setRange] = useState<TimeRange>("1M");
  const [view, setView] = useState<"value" | "sharePrice">("value");
  const chartRef = useRef<HTMLDivElement>(null);

  const data = useMemo(() => generateSampleData(range), [range]);

  const currentValue = data[data.length - 1]?.value ?? 0;
  const initialValue = data[0]?.value ?? 0;
  const changePct = initialValue > 0 ? ((currentValue - initialValue) / initialValue) * 100 : 0;
  const isPositive = changePct >= 0;

  const latestSharePrice = data[data.length - 1]?.sharePrice ?? 1;

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
          <h3 className="text-sm font-semibold">Strategy Performance</h3>
          <div className="flex items-center gap-4 mt-2">
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">Value</p>
              <p className="text-lg font-bold font-mono text-foreground">
                ${(currentValue / 1000).toFixed(2)}k
              </p>
            </div>
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">Change</p>
              <p
                className={`text-lg font-bold font-mono ${
                  isPositive ? "text-accent-green" : "text-accent-red"
                }`}
              >
                {isPositive ? "+" : ""}
                {changePct.toFixed(2)}%
              </p>
            </div>
            <div>
              <p className="text-[10px] text-muted uppercase tracking-wider">Share Price</p>
              <p className="text-lg font-bold font-mono text-foreground">
                {latestSharePrice.toFixed(4)}
              </p>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ChartExportButton chartRef={chartRef} filename="strategy-performance.png" />
          <div className="flex rounded-lg border border-card-border overflow-hidden">
            {rangeOptions.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  range === r
                    ? "bg-accent-green/15 text-accent-green"
                    : "bg-white/[0.02] text-muted hover:text-foreground"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-2 mb-3">
        <button
          onClick={() => setView("value")}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
            view === "value"
              ? "bg-accent-green/15 text-accent-green"
              : "bg-white/5 text-muted hover:text-foreground"
          }`}
        >
          Vault Value
        </button>
        <button
          onClick={() => setView("sharePrice")}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
            view === "sharePrice"
              ? "bg-accent-green/15 text-accent-green"
              : "bg-white/5 text-muted hover:text-foreground"
          }`}
        >
          Share Price
        </button>
      </div>

      <div ref={chartRef} className="h-72">
        {view === "value" ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="valueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="depositGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4488ff" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#4488ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
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
                  return [`$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`];
                }) as never}
              />
              <Legend
                wrapperStyle={{ fontSize: 11 }}
                formatter={(value: string) =>
                  value === "value" ? "Vault Value" : "Total Deposits"
                }
              />
              <Area
                type="monotone"
                dataKey="deposits"
                stroke="#4488ff"
                fill="url(#depositGradient)"
                strokeWidth={1.5}
                strokeDasharray="4 2"
                name="deposits"
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#22c55e"
                fill="url(#valueGradient)"
                strokeWidth={2}
                name="value"
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
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
                tickFormatter={(v: number) => v.toFixed(3)}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                labelStyle={{ color: "#888" }}
                formatter={((val: string | number | (string | number)[]) => {
                  const n = typeof val === "number" ? val : 0;
                  return [n.toFixed(4), "Share Price"];
                }) as never}
              />
              <Line
                type="monotone"
                dataKey="sharePrice"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: "#22c55e", stroke: "#0a0a0a", strokeWidth: 2 }}
                name="Share Price"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {vault && (
        <div className="flex gap-6 mt-3 text-xs text-muted">
          <span>
            Depositors: <span className="text-foreground font-mono">{vault.depositor_count}</span>
          </span>
          <span>
            Shares: <span className="text-foreground font-mono">{vault.total_shares.toFixed(2)}</span>
          </span>
          <span>
            APY:{" "}
            <span className={`font-mono ${vault.annualized_return >= 0 ? "text-accent-green" : "text-accent-red"}`}>
              {vault.annualized_return.toFixed(2)}%
            </span>
          </span>
        </div>
      )}
    </div>
  );
}
