"use client";

import { useState, useMemo, useRef } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { FundingRateEntry } from "@/lib/api";

interface FundingBarData {
  symbol: string;
  apy: number;
  rate: number;
}

function generateSampleData(): FundingBarData[] {
  const symbols = [
    { symbol: "BTC-PERP", apy: 45.2, rate: 0.0041 },
    { symbol: "ETH-PERP", apy: 32.8, rate: 0.003 },
    { symbol: "SOL-PERP", apy: -18.5, rate: -0.0017 },
    { symbol: "DOGE-PERP", apy: 125.3, rate: 0.0115 },
    { symbol: "ARB-PERP", apy: 78.4, rate: 0.0072 },
    { symbol: "AVAX-PERP", apy: -8.2, rate: -0.0008 },
    { symbol: "MATIC-PERP", apy: 56.1, rate: 0.0051 },
    { symbol: "LINK-PERP", apy: 22.7, rate: 0.0021 },
    { symbol: "UNI-PERP", apy: -12.4, rate: -0.0011 },
    { symbol: "AAVE-PERP", apy: 89.6, rate: 0.0082 },
    { symbol: "OP-PERP", apy: 34.5, rate: 0.0032 },
    { symbol: "NEAR-PERP", apy: -5.3, rate: -0.0005 },
    { symbol: "FIL-PERP", apy: 15.8, rate: 0.0015 },
    { symbol: "ATOM-PERP", apy: -22.1, rate: -0.002 },
    { symbol: "APT-PERP", apy: 67.3, rate: 0.0062 },
    { symbol: "SUI-PERP", apy: 102.4, rate: 0.0094 },
  ];
  return symbols;
}

type SortMode = "apy" | "symbol";

const tooltipStyle = {
  background: "rgba(17,17,17,0.95)",
  border: "1px solid #333",
  borderRadius: 8,
  fontSize: 12,
  color: "#e0e0e0",
  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
};

interface FundingChartProps {
  rates?: FundingRateEntry[];
  loading?: boolean;
}

export default function FundingChart({ rates, loading }: FundingChartProps) {
  const [sortMode, setSortMode] = useState<SortMode>("apy");
  const chartRef = useRef<HTMLDivElement>(null);

  const data = useMemo(() => {
    let raw: FundingBarData[];

    if (rates && rates.length > 0) {
      raw = rates.map((r) => ({
        symbol: r.symbol,
        apy: r.annualized_apy,
        rate: r.funding_rate,
      }));
    } else {
      raw = generateSampleData();
    }

    if (sortMode === "apy") {
      return [...raw].sort((a, b) => Math.abs(b.apy) - Math.abs(a.apy));
    }
    return [...raw].sort((a, b) => a.symbol.localeCompare(b.symbol));
  }, [rates, sortMode]);

  if (loading) {
    return (
      <div className="rounded-lg border border-card-border bg-card-bg p-5">
        <div className="skeleton h-8 w-48 mb-4" />
        <div className="skeleton h-72 w-full" />
      </div>
    );
  }

  const positiveCount = data.filter((d) => d.apy >= 0).length;
  const negativeCount = data.filter((d) => d.apy < 0).length;
  const avgApy = data.length > 0 ? data.reduce((s, d) => s + d.apy, 0) / data.length : 0;

  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">Funding Rates by Symbol</h3>
          <div className="flex items-center gap-4 mt-2 text-xs text-muted">
            <span>
              Positive:{" "}
              <span className="text-accent-green font-mono font-semibold">{positiveCount}</span>
            </span>
            <span>
              Negative:{" "}
              <span className="text-accent-red font-mono font-semibold">{negativeCount}</span>
            </span>
            <span>
              Avg APY:{" "}
              <span
                className={`font-mono font-semibold ${
                  avgApy >= 0 ? "text-accent-green" : "text-accent-red"
                }`}
              >
                {avgApy >= 0 ? "+" : ""}
                {avgApy.toFixed(1)}%
              </span>
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setSortMode("apy")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              sortMode === "apy"
                ? "bg-accent-green/15 text-accent-green"
                : "bg-white/5 text-muted hover:text-foreground"
            }`}
          >
            Sort by APY
          </button>
          <button
            onClick={() => setSortMode("symbol")}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              sortMode === "symbol"
                ? "bg-accent-green/15 text-accent-green"
                : "bg-white/5 text-muted hover:text-foreground"
            }`}
          >
            Sort by Symbol
          </button>
        </div>
      </div>

      <div ref={chartRef} className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barSize={20}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.06)"
              vertical={false}
            />
            <XAxis
              dataKey="symbol"
              tick={{ fill: "#888", fontSize: 9, angle: -45, textAnchor: "end" }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
              height={60}
              interval={0}
            />
            <YAxis
              tick={{ fill: "#888", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#888" }}
              formatter={((val: string | number | (string | number)[], name: string) => {
                  const n = typeof val === "number" ? val : 0;
                  if (name === "apy") {
                    return [`${n >= 0 ? "+" : ""}${n.toFixed(2)}% APY`, "Annualized"];
                  }
                  return [`${(n * 100).toFixed(4)}%`, "Funding Rate"];
                }) as never}
            />
            <Bar dataKey="apy" radius={[4, 4, 0, 0]} name="apy">
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.apy >= 0 ? "#22c55e" : "#ef4444"}
                  fillOpacity={0.3 + Math.min(Math.abs(entry.apy) / 200, 0.7)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center gap-4 mt-3 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-accent-green/60" /> Positive Funding
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-accent-red/60" /> Negative Funding
        </span>
        <span className="ml-auto">Bar opacity scales with APY magnitude</span>
      </div>
    </div>
  );
}
