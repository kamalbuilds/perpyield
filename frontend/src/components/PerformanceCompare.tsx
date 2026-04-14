"use client";

import { useMemo, useRef } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface StrategyPerformance {
  name: string;
  color: string;
  data: { date: string; returnPct: number }[];
}

function generateStrategyPerformances(): StrategyPerformance[] {
  const strategies = [
    { name: "Delta Neutral", color: "#22c55e", baseApy: 0.15, vol: 0.02 },
    { name: "Trend Following", color: "#4488ff", baseApy: 0.35, vol: 0.06 },
    { name: "Mean Reversion", color: "#a855f7", baseApy: 0.25, vol: 0.04 },
    { name: "Momentum Carry", color: "#f59e0b", baseApy: 0.45, vol: 0.08 },
  ];

  const days = 90;
  const now = Date.now();
  const msPerDay = 86400000;

  return strategies.map((s) => {
    const points: { date: string; returnPct: number }[] = [];
    let cumReturn = 0;

    for (let i = 0; i <= days; i++) {
      const d = new Date(now - (days - i) * msPerDay);
      const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
      const dailyReturn = (s.baseApy / 365) + (Math.random() - 0.5) * s.vol;
      cumReturn += dailyReturn;
      points.push({ date: label, returnPct: Math.round(cumReturn * 10000) / 100 });
    }
    return { name: s.name, color: s.color, data: points };
  });
}

const tooltipStyle = {
  background: "rgba(17,17,17,0.95)",
  border: "1px solid #333",
  borderRadius: 8,
  fontSize: 12,
  color: "#e0e0e0",
  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
};

export default function PerformanceCompare() {
  const chartRef = useRef<HTMLDivElement>(null);

  const strategies = useMemo(() => generateStrategyPerformances(), []);

  const allDates = strategies[0]?.data.map((d) => d.date) ?? [];

  const chartData = useMemo(() => {
    return allDates.map((date, i) => {
      const point: Record<string, string | number> = { date };
      strategies.forEach((s) => {
        point[s.name] = s.data[i]?.returnPct ?? 0;
      });
      return point;
    });
  }, [allDates, strategies]);

  const finalReturns = strategies.map((s) => ({
    name: s.name,
    color: s.color,
    returnPct: s.data[s.data.length - 1]?.returnPct ?? 0,
  }));

  return (
    <div className="rounded-lg border border-card-border bg-card-bg p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">Strategy Comparison</h3>
          <p className="text-xs text-muted mt-1">90-day cumulative return</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {finalReturns.map((s) => (
          <div
            key={s.name}
            className="rounded-lg border border-card-border/50 bg-white/[0.02] p-3"
          >
            <div className="flex items-center gap-2 mb-1">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: s.color }}
              />
              <p className="text-[10px] text-muted uppercase tracking-wider truncate">
                {s.name}
              </p>
            </div>
            <p
              className="text-lg font-bold font-mono"
              style={{ color: s.returnPct >= 0 ? "#22c55e" : "#ef4444" }}
            >
              {s.returnPct >= 0 ? "+" : ""}
              {s.returnPct.toFixed(2)}%
            </p>
          </div>
        ))}
      </div>

      <div ref={chartRef} className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
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
              tickFormatter={(v: number) => `${v.toFixed(1)}%`}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelStyle={{ color: "#888" }}
              formatter={((val: string | number | (string | number)[]) => {
                  const n = typeof val === "number" ? val : 0;
                  return [`${n >= 0 ? "+" : ""}${n.toFixed(2)}%`];
                }) as never}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
              iconType="circle"
              iconSize={8}
            />
            {strategies.map((s) => (
              <Line
                key={s.name}
                type="monotone"
                dataKey={s.name}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: s.color, stroke: "#0a0a0a", strokeWidth: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
