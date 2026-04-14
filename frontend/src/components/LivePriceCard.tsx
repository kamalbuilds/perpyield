"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  AreaChart,
  Area,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { usePrices, type SymbolPrice } from "@/context/PriceContext";

interface LivePriceCardProps {
  symbol: string;
  onSelectSymbol?: (symbol: string) => void;
}

function formatPrice(price: number): string {
  if (price >= 1000) {
    return price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  if (price >= 1) {
    return price.toFixed(4);
  }
  return price.toFixed(6);
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-card-bg border border-card-border rounded px-2 py-1 text-xs font-mono text-foreground">
      ${formatPrice(payload[0].value)}
    </div>
  );
}

export default function LivePriceCard({
  symbol,
  onSelectSymbol,
}: LivePriceCardProps) {
  const { prices, history, connected } = usePrices();
  const price: SymbolPrice | null = prices[symbol] ?? null;
  const priceHistory = history[symbol] ?? [];
  const [hovering, setHovering] = useState(false);

  const markPrice = price?.price ?? 0;
  const change24hPct = price?.change24hPct ?? 0;
  const fundingRate = price?.fundingRate ?? 0;
  const bid = price?.bid ?? 0;
  const ask = price?.ask ?? 0;
  const spread = price?.spread ?? 0;
  const spreadPct = price?.spreadPct ?? 0;
  const isPositive = change24hPct >= 0;

  const label = symbol.replace("-PERP", "");

  const chartData = priceHistory.map((p) => ({
    price: p.price,
  }));

  const chartMin =
    chartData.length > 0
      ? Math.min(...chartData.map((d) => d.price)) * 0.9995
      : 0;
  const chartMax =
    chartData.length > 0
      ? Math.max(...chartData.map((d) => d.price)) * 1.0005
      : 1;

  const gradientId = `sparkGrad-${symbol}`;
  const strokeColor = isPositive ? "#00ff88" : "#ff4444";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      className="rounded-xl border border-card-border bg-card-bg overflow-hidden"
    >
      <div className="px-5 pt-5 pb-2">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold">{label}</h3>
            <span className="text-xs text-muted font-mono">{symbol}</span>
          </div>
          <span className="flex items-center gap-1.5 text-[10px] text-muted">
            <span
              className={`inline-block w-1.5 h-1.5 rounded-full ${
                connected ? "bg-accent-green animate-pulse" : "bg-accent-red"
              }`}
            />
            {connected ? "LIVE" : "OFFLINE"}
          </span>
        </div>

        <div className="flex items-end gap-3 mb-1">
          <motion.span
            key={markPrice}
            initial={{ opacity: 0.7, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="text-3xl font-bold font-mono tracking-tight"
          >
            ${formatPrice(markPrice)}
          </motion.span>
          <motion.span
            animate={{ color: isPositive ? "#00ff88" : "#ff4444" }}
            className="text-sm font-mono font-semibold mb-0.5"
          >
            {isPositive ? "+" : ""}
            {change24hPct.toFixed(2)}%
          </motion.span>
        </div>

        <div className="flex items-center gap-4 text-xs text-muted font-mono">
          <span>
            Funding:{" "}
            <span
              className={
                fundingRate >= 0 ? "text-accent-green" : "text-accent-red"
              }
            >
              {fundingRate >= 0 ? "+" : ""}
              {(fundingRate * 100).toFixed(4)}%
            </span>
          </span>
          <span>
            Spread: {spreadPct.toFixed(3)}%
          </span>
        </div>
      </div>

      <div className="px-2 py-1 h-24">
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={strokeColor} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis
                domain={[chartMin, chartMax]}
                hide
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="price"
                stroke={strokeColor}
                strokeWidth={1.5}
                fill={`url(#${gradientId})`}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-xs text-muted">
            Waiting for price data...
          </div>
        )}
      </div>

      <div className="px-5 pb-3 flex items-center gap-2 text-xs font-mono text-muted">
        <span>Bid: ${formatPrice(bid)}</span>
        <span className="text-card-border">|</span>
        <span>Ask: ${formatPrice(ask)}</span>
        <span className="text-card-border">|</span>
        <span>Spread: ${spread.toFixed(4)}</span>
      </div>

      <div className="px-5 pb-5 flex gap-3">
        <button className="flex-1 py-2.5 rounded-lg text-sm font-semibold bg-accent-green/10 text-accent-green border border-accent-green/20 hover:bg-accent-green/20 transition-colors">
          Buy / Long
        </button>
        <button className="flex-1 py-2.5 rounded-lg text-sm font-semibold bg-accent-red/10 text-accent-red border border-accent-red/20 hover:bg-accent-red/20 transition-colors">
          Sell / Short
        </button>
      </div>

      {onSelectSymbol && hovering && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 bg-black/50 flex items-center justify-center cursor-pointer"
          onClick={() => onSelectSymbol(symbol)}
        >
          <span className="text-sm font-semibold text-foreground">
            View Details
          </span>
        </motion.div>
      )}
    </motion.div>
  );
}
